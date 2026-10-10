import { afterEach, describe, expect, test } from 'bun:test'
import { cp, mkdtemp, readFile, rm, writeFile, readdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { initSkill } from '../plugins/skill-creator/skills/skill-creator/scripts/init_skill'
import { validateSkill } from '../plugins/skill-creator/skills/skill-creator/scripts/quick_validate'
import { writeOpenaiYaml } from '../plugins/skill-creator/skills/skill-creator/scripts/generate_openai_yaml'

const temporary: string[] = []
afterEach(async () => { for (const root of temporary.splice(0)) await rm(root, { recursive: true, force: true }) })
const root = async () => { const value = await mkdtemp(join(tmpdir(), 'haivex-creator-test-')); temporary.push(value); return value }

describe('技能创建器的 TypeScript 移植', () => {
  test('最小初始化、不覆盖、补完后通过格式检查', async () => {
    const parent = await root()
    const directory = await initSkill('Weekly Report', parent, [], false, ['display_name=周报整理', 'short_description=整理本周工作进展'])
    expect((await readdir(directory)).sort()).toEqual(['SKILL.md', 'agents'])
    expect((await validateSkill(directory)).valid).toBe(false)
    await expect(initSkill('weekly-report', parent)).rejects.toThrow()
    await writeFile(join(directory, 'SKILL.md'), '---\nname: weekly-report\ndescription: 在用户要求整理周报时汇总其提供的工作记录。\n---\n\n按来源归纳本周进展与待办。\n')
    expect((await validateSkill(directory)).valid).toBe(true)
    expect(await readFile(join(directory, 'agents/openai.yaml'), 'utf8')).toContain('周报整理')
  })
  test('只创建请求的资源，范例脚本不依赖 Python', async () => {
    const directory = await initSkill('helper', await root(), ['scripts', 'references'], true)
    expect((await readdir(directory)).sort()).toEqual(['SKILL.md', 'agents', 'references', 'scripts'])
    expect(await readdir(join(directory, 'scripts'))).toEqual(['example.ts'])
  })
  test('已下载创建器的 CLI 脱离仓库后仍可生成技能', async () => {
    const parent = await root(), installed = join(parent, 'skill-creator')
    await cp(resolve(import.meta.dir, '../plugins/skill-creator/skills/skill-creator'), installed, { recursive: true })
    const child = Bun.spawn([process.execPath, '--no-install', join(installed, 'scripts/init_skill.ts'), 'portable-skill', '--path', join(parent, 'skills'), '--interface', 'display_name=便携技能'], { cwd: parent, stdout: 'pipe', stderr: 'pipe' })
    const [stdout, stderr, code] = await Promise.all([new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited])
    expect({ code, stderr }).toEqual({ code: 0, stderr: '' })
    expect(stdout).toContain('portable-skill')
    expect(await readFile(join(parent, 'skills/portable-skill/agents/openai.yaml'), 'utf8')).toContain('便携技能')
  })
  test('UI 元数据更新保留策略、依赖和未指定字段', async () => {
    const directory = await initSkill('helper', await root())
    await writeFile(join(directory, 'agents/openai.yaml'), 'interface:\n  display_name: "原名称"\n  short_description: "原有说明"\n  icon_small: "./assets/icon.png"\npolicy:\n  allow_implicit_invocation: false\ndependencies:\n  tools: []\n')
    await writeOpenaiYaml(directory, 'helper', ['short_description=更新后的说明'])
    const parsed = Bun.YAML.parse(await readFile(join(directory, 'agents/openai.yaml'), 'utf8')) as any
    expect(parsed.interface).toEqual({ display_name: '原名称', short_description: '更新后的说明', icon_small: './assets/icon.png' })
    expect(parsed.policy.allow_implicit_invocation).toBe(false)
    expect(parsed.dependencies).toEqual({ tools: [] })
  })
})
