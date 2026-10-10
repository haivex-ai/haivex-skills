// Adapted from OpenAI skill-creator (Apache-2.0); Haivex TypeScript/Bun port.
import { mkdir, writeFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { homedir } from 'node:os'
import { parseArgs } from 'node:util'
import { displayName, interfaceValues, writeOpenaiYaml } from './generate_openai_yaml'

export const initSkill = async (input: string, root: string, resources: string[] = [], examples = false, overrides: string[] = []) => {
  const name = input.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  if (!name || name.length > 64) throw new Error('技能名称需为 1–64 位英文、数字或连字符；中文显示名用 --interface display_name=...')
  const directories = [...new Set(resources.filter(Boolean))]
  if (directories.some((item) => !['scripts', 'references', 'assets'].includes(item))) throw new Error('resources 仅支持 scripts,references,assets')
  interfaceValues(name, overrides)
  const directory = join(resolve(root), name)
  await mkdir(resolve(root), { recursive: true })
  // 不覆盖已有目录，避免丢失用户已创建的技能或资源。
  await mkdir(directory)
  await writeFile(join(directory, 'SKILL.md'), `---\nname: ${name}\ndescription: "[TODO: 简要说明技能做什么、何时适用。]"\n---\n\n# ${displayName(name)}\n\n[TODO: 添加 Haivex 执行任务所需的具体指导，仅在相关时引用资源。]\n`, { flag: 'wx' })
  await writeOpenaiYaml(directory, name, overrides)
  for (const resource of directories) {
    await mkdir(join(directory, resource))
    if (!examples) continue
    const filename = resource === 'scripts' ? 'example.ts' : resource === 'references' ? 'reference.md' : 'example_asset.txt'
    const content = resource === 'scripts' ? `// 替换为实际实现，不需要时删除。\nconsole.log(${JSON.stringify(`Example for ${name}`)})\n` : `# ${displayName(name)}\n\n替换为任务确实需要的${resource === 'references' ? '参考资料' : '模板或素材'}，不需要时删除。\n`
    await writeFile(join(directory, resource, filename), content, { flag: 'wx' })
  }
  return directory
}

if (import.meta.main) {
  try {
    const { positionals, values } = parseArgs({ args: Bun.argv.slice(2), allowPositionals: true, options: { path: { type: 'string' }, resources: { type: 'string' }, examples: { type: 'boolean' }, interface: { type: 'string', multiple: true } } })
    if (positionals.length !== 1) throw new Error('用法：bun init_skill.ts <skill-name> [--path directory] [--resources scripts,references,assets] [--examples] [--interface key=value]')
    console.log(await initSkill(positionals[0]!, values.path ?? join(homedir(), '.multi-agents/skills'), (values.resources ?? '').split(',').map((s) => s.trim()), values.examples, values.interface))
    console.log('请补完 SKILL.md 并运行 quick_validate.ts；草稿不会出现在可用技能中。')
  } catch (error) { console.error(String(error)); process.exitCode = 1 }
}
