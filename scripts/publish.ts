/** 技能源码与发布包分开：只有完成上传的 GitHub Release 才对客户端可见。 */
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile, open, lstat } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { tmpdir } from 'node:os'
import { zipSync, unzipSync, type Zippable } from 'fflate'
import { validateSkill } from '../plugins/skill-creator/skills/skill-creator/scripts/quick_validate'

export const REPOSITORY = 'haivex-ai/haivex-skills'
const MARKETPLACE = '.agents/plugins/marketplace.json'
const identifier = /^[a-z0-9]+(?:-[a-z0-9]+)*$/
const object = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('清单格式无效')
  return value as Record<string, unknown>
}
export const versionParts = (value: unknown): number[] => {
  if (typeof value !== 'string' || !/^\d+\.\d+\.\d+$/.test(value)) throw new Error('版本必须为 major.minor.patch')
  const parts = value.split('.').map(Number)
  if (!parts.every(Number.isSafeInteger)) throw new Error('版本号超出范围')
  return parts
}
export const nextVersion = (value: unknown) => {
  const parts = versionParts(value)
  parts[2]!++
  const next = parts.join('.')
  versionParts(next)
  return next
}
const command = (cwd: string, executable: string, args: string[]) => {
  const result = spawnSync(executable, args, { cwd, maxBuffer: 90 * 1024 * 1024, timeout: 120_000 })
  if (result.error || result.status !== 0) throw new Error(`${executable} ${args[0]} 失败：${result.error?.message ?? result.stderr?.toString().trim()}`)
  return result.stdout
}
const git = (cwd: string, ...args: string[]) => command(cwd, 'git', args).toString().trim()
const gh = (cwd: string, ...args: string[]) => command(cwd, 'gh', args).toString().trim()

export const collectFiles = async (root: string, id: string) => {
  if (!identifier.test(id) || id.length > 64) throw new Error('插件标识无效')
  const files: Record<string, Uint8Array> = { [MARKETPLACE]: await readFile(join(root, MARKETPLACE)) }
  const visit = async (relative: string) => {
    const info = await lstat(join(root, relative))
    if (info.isSymbolicLink()) throw new Error(`发布包不能包含符号链接：${relative}`)
    if (info.isDirectory()) {
      for (const entry of await readdir(join(root, relative))) {
        if (entry === '.DS_Store') continue
        if (entry === 'node_modules' || entry === '.git' || entry.startsWith('.env')) throw new Error(`请移除非发布文件：${entry}`)
        await visit(`${relative}/${entry}`)
      }
    } else if (info.isFile()) files[relative] = await readFile(join(root, relative))
    else throw new Error(`发布包只支持普通文件：${relative}`)
  }
  await visit(`plugins/${id}`)
  return files
}

export const buildPackage = async (files: Record<string, Uint8Array>, id: string, revision: string) => {
  if (!identifier.test(id) || id.length > 64 || !/^[a-f0-9]{40}$/.test(revision)) throw new Error('插件或提交标识无效')
  const json = (path: string) => object(JSON.parse(Buffer.from(files[path] ?? []).toString('utf8')))
  const manifest = json(`plugins/${id}/plugin.json`)
  if (manifest.name !== id) throw new Error('插件名称与目录不一致')
  versionParts(manifest.version)
  const version = manifest.version as string
  const marketplace = json(MARKETPLACE)
  if (!Array.isArray(marketplace.plugins)) throw new Error('市场目录无效')
  const matches = marketplace.plugins.filter((entry) => object(entry).name === id)
  if (matches.length !== 1) throw new Error('市场必须有且只有一个对应插件条目')
  const entry = object(matches[0]), source = object(entry.source)
  if (source.source !== 'local' || source.path !== `./plugins/${id}`) throw new Error('市场条目必须指向对应的本仓库插件目录')
  if (object(entry.policy ?? {}).installation === 'NOT_AVAILABLE') throw new Error('已下架插件不能发布')
  const prefix = `haivex-skills-${revision}/`
  const entries: Zippable = {}
  const seen = new Set<string>(), skillFiles = new Map<string, number>()
  let total = 0
  const temporary = await mkdtemp(join(tmpdir(), 'haivex-skill-pack-'))
  try {
    for (const [name, bytes] of Object.entries(files).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)) {
      if (name !== MARKETPLACE && !name.startsWith(`plugins/${id}/`)) continue
      const parts = name.split('/')
      if (parts.some((part) => !part || part === '.' || part === '..' || /[\\:\x00]/.test(part) || /[. ]$/.test(part) || /^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(part))) throw new Error('发布文件路径无效')
      if (seen.has(name.toLowerCase())) throw new Error('发布文件大小写冲突')
      seen.add(name.toLowerCase())
      if (parts.some((part) => part === '.git' || part === 'node_modules' || part.startsWith('.env') || part.toLowerCase() === '.haivex-install.json')) throw new Error('发布包包含本地文件')
      total += bytes.length
      if (total > 80 * 1024 * 1024 || seen.size > 5000) throw new Error('发布包解压后过大')
      const skill = /^plugins\/[^/]+\/skills\/([^/]+)\/(.+)$/.exec(name)
      if (skill) {
        if (!identifier.test(skill[1]!) || skill[1]!.length > 64) throw new Error('技能名称无效')
        skillFiles.set(skill[1]!, (skillFiles.get(skill[1]!) ?? 0) + 1)
        if (skill[2] === 'SKILL.md' || skill[2] === 'README.md' || skill[2] === 'agents/openai.yaml') {
          if (bytes.length > 128 * 1024) throw new Error('技能说明文件过大')
          if (skill[2].endsWith('.yaml')) Bun.YAML.parse(Buffer.from(bytes).toString('utf8'))
        }
      }
      const value = name === MARKETPLACE ? Buffer.from(JSON.stringify({ ...marketplace, plugins: [entry] }, null, 2) + '\n') : bytes
      entries[prefix + name] = [value, { mtime: new Date(2026, 0, 1) }]
      await mkdir(join(temporary, ...parts.slice(0, -1)), { recursive: true })
      await writeFile(join(temporary, name), value)
    }
    if (!skillFiles.size) throw new Error('插件中没有技能')
    for (const [skill, count] of skillFiles) {
      if (count > 300) throw new Error('单个技能文件过多')
      const result = await validateSkill(join(temporary, 'plugins', id, 'skills', skill))
      if (!result.valid) throw new Error(result.message)
    }
    const bytes = zipSync(entries)
    if (bytes.length > 20 * 1024 * 1024) throw new Error('发布包超过 20 MiB')
    return { id, version, revision, tag: `${id}@${version}`, filename: `${id}-${version}.zip`, bytes, sha256: createHash('sha256').update(bytes).digest('hex') }
  } finally { await rm(temporary, { recursive: true, force: true }) }
}

type Release = { tag_name: string; draft: boolean; prerelease: boolean; target_commitish: string; assets: Array<{ name: string; size: number; digest: string | null }> }
export const publish = async (root: string, id: string, options: { packOnly?: boolean; noBump?: boolean } = {}) => {
  const preview = await buildPackage(await collectFiles(root, id), id, git(root, 'rev-parse', 'HEAD'))
  await mkdir(join(root, 'dist'), { recursive: true })
  if (options.packOnly) {
    const path = join(root, 'dist', preview.filename)
    await writeFile(path, preview.bytes)
    console.log(`本地预览包：${path}（未升版本、未提交、未发布）`)
    return preview
  }
  const lock = await open(join(root, '.git', 'haivex-skill-publish.lock'), 'wx').catch(() => { throw new Error('已有发布任务，或上次中断留下 .git/haivex-skill-publish.lock；确认无任务运行后再移除') })
  try {
    if (git(root, 'branch', '--show-current') !== 'main') throw new Error('请在 main 分支发布')
    if (git(root, 'diff', '--cached', '--name-only')) throw new Error('请先处理暂存区，发布命令只提交目标插件与市场目录')
    const remote = git(root, 'remote', 'get-url', 'origin')
    if (!/github\.com(?::443)?[/:]haivex-ai\/haivex-skills(?:\.git)?$/.test(remote)) throw new Error('origin 必须指向 haivex-ai/haivex-skills')
    console.log('检查 GitHub 权限与远端版本…')
    gh(root, 'auth', 'status')
    git(root, 'fetch', 'origin', 'main')
    git(root, 'merge-base', '--is-ancestor', 'origin/main', 'HEAD')
    const releases = (JSON.parse(gh(root, 'api', `repos/${REPOSITORY}/releases?per_page=100`, '--paginate', '--slurp')) as Release[][]).flat()
    const version = options.noBump ? preview.version : nextVersion(preview.version)
    const tag = `${id}@${version}`
    const existing = releases.find((release) => release.tag_name === tag)
    if (!existing) {
      const parts = versionParts(version)
      for (const release of releases.filter((item) => !item.draft && !item.prerelease && item.tag_name.startsWith(`${id}@`))) {
        const old = versionParts(release.tag_name.slice(id.length + 1))
        const difference = parts.map((part, index) => part - old[index]!).find((value) => value !== 0) ?? 0
        if (difference <= 0) throw new Error(`版本必须高于已发布的 ${release.tag_name}`)
      }
    }
    if (version !== preview.version) {
      const path = join(root, 'plugins', id, 'plugin.json')
      const manifest = JSON.parse(await readFile(path, 'utf8'))
      await writeFile(path, JSON.stringify({ ...manifest, version }, null, 2) + '\n')
    }
    // 先验证待提交内容，再从 Git 提交生成最终包，保证发布内容可追溯。
    await buildPackage(await collectFiles(root, id), id, git(root, 'rev-parse', 'HEAD'))
    git(root, 'add', '--', `plugins/${id}`, MARKETPLACE)
    if (git(root, 'diff', '--cached', '--name-only')) git(root, 'commit', '-m', `Release ${tag}`)
    const revision = existing?.target_commitish ?? git(root, 'rev-parse', 'HEAD')
    if (!/^[a-f0-9]{40}$/.test(revision)) throw new Error('已存在发布的提交标识无效')
    if (existing && git(root, 'diff', revision, '--', `plugins/${id}`, MARKETPLACE)) throw new Error('此版本已创建且内容不同，请发布新版本')
    const archive = command(root, 'git', ['archive', '--format=zip', revision, '--', `plugins/${id}`, MARKETPLACE])
    const packed = await buildPackage(unzipSync(archive, { filter: (entry) => !entry.name.endsWith('/') }), id, revision)
    if (packed.version !== version) throw new Error('提交内版本与发布版本不一致')
    const path = join(root, 'dist', packed.filename)
    await writeFile(path, packed.bytes)
    const matching = (asset: Release['assets'][number]) => asset.name === packed.filename && asset.size === packed.bytes.length && asset.digest === `sha256:${packed.sha256}`
    if (existing && !existing.draft) {
      if (!existing.assets.some(matching)) throw new Error('已发布版本与本地包不同，禁止覆盖')
      console.log(`版本已发布：https://github.com/${REPOSITORY}/releases/tag/${encodeURIComponent(tag)}`)
      return packed
    }
    console.log(`推送源码并上传 ${tag}…`)
    git(root, 'push', 'origin', 'main')
    if (!existing) gh(root, 'release', 'create', tag, '--repo', REPOSITORY, '--target', revision, '--title', tag, '--notes', `发布 ${id} ${version}。`, '--draft')
    const prior = existing?.assets.find((asset) => asset.name === packed.filename)
    if (prior && !matching(prior)) throw new Error('草稿附件与本地包不同，未覆盖；请检查该草稿')
    if (!prior) gh(root, 'release', 'upload', tag, path, '--repo', REPOSITORY)
    // 按标签查询的 REST 接口不返回草稿，上传后仍从维护者可见的列表中核对。
    const uploaded = (JSON.parse(gh(root, 'api', `repos/${REPOSITORY}/releases?per_page=100`, '--paginate', '--slurp')) as Release[][]).flat().find((release) => release.tag_name === tag)
    if (!uploaded?.assets.some(matching)) throw new Error('GitHub 附件摘要或大小不一致，保留草稿，请用 --no-bump 重试')
    gh(root, 'release', 'edit', tag, '--repo', REPOSITORY, '--draft=false', '--latest=false')
    console.log(`已发布：https://github.com/${REPOSITORY}/releases/tag/${encodeURIComponent(tag)}`)
    return packed
  } finally { await lock.close(); await rm(join(root, '.git', 'haivex-skill-publish.lock'), { force: true }) }
}

if (import.meta.main) {
  const args = Bun.argv.slice(2)
  if (args.includes('--help')) console.log('用法：bun run publish <插件名> [--no-bump]\n本地预览：bun run pack <插件名>\n默认自动 patch +1、提交目标插件、推送 main、打包并发布 GitHub Release。--no-bump 用于首次发布当前版本或失败重试。')
  else {
    const id = args.find((arg) => !arg.startsWith('--'))
    if (!id || args.some((arg) => arg !== id && arg !== '--pack-only' && arg !== '--no-bump')) throw new Error('参数无效，请运行 bun run publish --help')
    try { await publish(resolve(import.meta.dir, '..'), id, { packOnly: args.includes('--pack-only'), noBump: args.includes('--no-bump') }) }
    catch (error) { console.error(error instanceof Error ? error.message : error); console.error('若版本已递增或上传中断，可用同一命令加 --no-bump 重试；不会覆盖已发布包。'); process.exitCode = 1 }
  }
}
