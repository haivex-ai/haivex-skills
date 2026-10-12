import { afterEach, expect, test } from 'bun:test'
import { mkdir, mkdtemp, rm, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { strToU8, unzipSync } from 'fflate'
import { buildPackage, collectFiles, nextVersion } from '../scripts/publish'

const roots: string[] = []
afterEach(async () => { for (const path of roots.splice(0)) await rm(path, { recursive: true, force: true }) })
const revision = 'a'.repeat(40)
const base = () => ({
  '.agents/plugins/marketplace.json': strToU8(JSON.stringify({ name: 'haivex-official', plugins: ['example', 'other'].map((name) => ({ name, source: { source: 'local', path: `./plugins/${name}` } })) })),
  'plugins/example/plugin.json': strToU8(JSON.stringify({ name: 'example', version: '1.0.0' })),
  'plugins/example/skills/example/SKILL.md': strToU8('---\nname: example\ndescription: 处理用户提供的资料。\n---\n\n按用户要求整理。\n'),
})

test('发包只包含目标插件，二进制资源字节保持原样，包可重复生成', async () => {
  const overview = strToU8('介绍用途、所需资料和交付结果。')
  const files = { ...base(), 'plugins/example/skills/example/README.md': overview, 'plugins/example/skills/example/templates/table.xlsx': new Uint8Array([0, 255, 128, 2]), 'plugins/other/secret.txt': strToU8('other') }
  const first = await buildPackage(files, 'example', revision), second = await buildPackage(files, 'example', revision)
  expect(first.sha256).toBe(second.sha256)
  expect(first.tag).toBe('example@1.0.0')
  const extracted = unzipSync(first.bytes), prefix = `haivex-skills-${revision}/`
  expect(extracted[`${prefix}plugins/example/skills/example/templates/table.xlsx`]).toEqual(files['plugins/example/skills/example/templates/table.xlsx'])
  expect(extracted[`${prefix}plugins/example/skills/example/README.md`]).toEqual(overview)
  expect(Object.keys(extracted).some((path) => path.includes('plugins/other'))).toBe(false)
  const marketplace = JSON.parse(Buffer.from(extracted[`${prefix}.agents/plugins/marketplace.json`]!).toString())
  expect(marketplace.plugins.map((entry: { name: string }) => entry.name)).toEqual(['example'])
})

test('版本自动递增，拒绝无效或溢出的版本', () => {
  expect(nextVersion('1.0.9')).toBe('1.0.10')
  for (const value of ['1.0', '1.0.beta', '1.0.9007199254740991']) expect(() => nextVersion(value)).toThrow()
})

test('拒绝目录错配、未完成内容、安装标记、越界与重名文件', async () => {
  for (const files of [
    { ...base(), 'plugins/example/plugin.json': strToU8('{"name":"other","version":"1.0.0"}') },
    { ...base(), 'plugins/example/skills/example/SKILL.md': strToU8('empty') },
    { ...base(), 'plugins/example/skills/example/.haivex-install.json': strToU8('{}') },
    { ...base(), 'plugins/example/skills/example/../escape': strToU8('escape') },
    { ...base(), 'plugins/example/skills/example/skill.md': strToU8('duplicate') },
    { ...base(), 'plugins/example/skills/example/README.md': strToU8('x'.repeat(128 * 1024 + 1)) },
  ]) await expect(buildPackage(files, 'example', revision)).rejects.toThrow()
})

test('本地收集拒绝符号链接，不把外部文件打进包', async () => {
  const root = await mkdtemp(join(tmpdir(), 'haivex-publish-test-')); roots.push(root)
  for (const [name, bytes] of Object.entries(base())) { await mkdir(join(root, name, '..'), { recursive: true }); await writeFile(join(root, name), bytes) }
  await symlink('/etc/hosts', join(root, 'plugins/example/external'))
  await expect(collectFiles(root, 'example')).rejects.toThrow('符号链接')
})

test('一条命令自动升版并提交；上传失败保留草稿，重试后才正式发布且不覆盖', async () => {
  const { spawnSync } = await import('node:child_process')
  const { readFile, chmod } = await import('node:fs/promises')
  const { publish } = await import('../scripts/publish')
  const parent = await mkdtemp(join(tmpdir(), 'haivex-publish-flow-')); roots.push(parent)
  const root = join(parent, 'source'), remote = join(parent, 'remote.git'), bin = join(parent, 'bin'), state = join(parent, 'state.json')
  await mkdir(root); await mkdir(bin)
  const runGit = (cwd: string, ...args: string[]) => {
    const result = spawnSync('/usr/bin/git', args, { cwd, encoding: 'utf8' })
    if (result.status !== 0) throw new Error(result.stderr)
    return result.stdout.trim()
  }
  runGit(parent, 'init', '--bare', remote)
  runGit(root, 'init', '-b', 'main')
  runGit(root, 'config', 'user.name', 'Publish test'); runGit(root, 'config', 'user.email', 'test@example.invalid')
  for (const [name, bytes] of Object.entries(base())) { await mkdir(join(root, name, '..'), { recursive: true }); await writeFile(join(root, name), bytes) }
  runGit(root, 'add', '.'); runGit(root, 'commit', '-m', 'Initial test skills')
  runGit(root, 'remote', 'add', 'origin', remote); runGit(root, 'push', '-u', 'origin', 'main')
  await writeFile(join(root, 'unrelated.txt'), '用户未提交的其他工作')
  await writeFile(state, JSON.stringify({ failUpload: true, release: null, uploads: 0 }))
  const executable = (path: string, body: string) => writeFile(path, `#!${process.execPath}\n${body}`).then(() => chmod(path, 0o755))
  await executable(join(bin, 'git'), `
    const args=process.argv.slice(2);
    if(args.join(' ')==='remote get-url origin') console.log('https://github.com/haivex-ai/haivex-skills.git');
    else { const result=Bun.spawnSync(['/usr/bin/git',...args]); process.stdout.write(result.stdout); process.stderr.write(result.stderr); process.exit(result.exitCode); }
  `)
  await executable(join(bin, 'gh'), `
    import {readFileSync,writeFileSync} from 'node:fs';
    import {createHash} from 'node:crypto';
    const path=${JSON.stringify(state)}, state=JSON.parse(readFileSync(path,'utf8')), args=process.argv.slice(2);
    const save=()=>writeFileSync(path,JSON.stringify(state));
    if(args[0]==='auth') process.exit(0);
    if(args[0]==='api') {
      if(args[1].includes('/releases/tags/')) { console.error('草稿不支持按标签查询'); process.exit(1); }
      else console.log(JSON.stringify([state.release ? [state.release] : []]));
    } else if(args[1]==='create') {state.release={tag_name:args[2],target_commitish:args[args.indexOf('--target')+1],draft:true,prerelease:false,assets:[]};save();}
    else if(args[1]==='upload') {
      if(state.failUpload){state.failUpload=false;save();console.error('模拟网络中断');process.exit(1);}
      const file=args[3],bytes=readFileSync(file);state.uploads++;state.release.assets.push({name:file.split('/').at(-1),size:bytes.length,digest:'sha256:'+createHash('sha256').update(bytes).digest('hex')});save();
    } else if(args[1]==='edit') {state.release.draft=false;save();}
    else throw new Error('未预期调用：'+args.join(' '));
  `)
  const priorPath = process.env.PATH
  process.env.PATH = `${bin}:${priorPath}`
  try {
    await expect(publish(root, 'example')).rejects.toThrow('模拟网络中断')
    expect(JSON.parse(await readFile(join(root, 'plugins/example/plugin.json'), 'utf8')).version).toBe('1.0.1')
    expect(JSON.parse(await readFile(state, 'utf8')).release.draft).toBe(true)
    const packed = await publish(root, 'example', { noBump: true })
    expect(packed.version).toBe('1.0.1')
    const result = JSON.parse(await readFile(state, 'utf8'))
    expect(result.release.draft).toBe(false)
    expect(result.uploads).toBe(1)
    expect(runGit(root, 'status', '--short')).toContain('?? unrelated.txt')
    expect(runGit(root, 'log', '-1', '--format=%s')).toBe('Release example@1.0.1')
    await publish(root, 'example', { noBump: true })
    expect(JSON.parse(await readFile(state, 'utf8')).uploads).toBe(1)
  } finally { process.env.PATH = priorPath }
})
