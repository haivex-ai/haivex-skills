// Adapted from OpenAI skill-creator (Apache-2.0); Haivex TypeScript/Bun port.
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { parseArgs } from 'node:util'

const allowed = new Set(['display_name', 'short_description', 'icon_small', 'icon_large', 'brand_color', 'default_prompt'])
const acronyms = new Set(['GH', 'MCP', 'API', 'CI', 'CLI', 'LLM', 'PDF', 'PR', 'UI', 'URL', 'SQL'])
const brands: Record<string, string> = { openai: 'OpenAI', openapi: 'OpenAPI', github: 'GitHub', pagerduty: 'PagerDuty', datadog: 'DataDog', sqlite: 'SQLite', fastapi: 'FastAPI', haivex: 'Haivex' }
export const displayName = (name: string) => name.split('-').map((word, index) =>
  acronyms.has(word.toUpperCase()) ? word.toUpperCase() : brands[word] ?? (index > 0 && ['and', 'or', 'to', 'up', 'with'].includes(word) ? word : word[0]!.toUpperCase() + word.slice(1))).join(' ')

export const interfaceValues = (name: string, overrides: string[]) => {
  const values: Record<string, string> = {}
  for (const entry of overrides) {
    const equal = entry.indexOf('=')
    const key = entry.slice(0, equal).trim()
    if (equal < 1 || !allowed.has(key)) throw new Error(`无效的界面字段：${entry}，请使用 --interface key=value`)
    values[key] = entry.slice(equal + 1).trim()
  }
  values.display_name ||= displayName(name)
  values.short_description ||= `帮助完成${values.display_name}相关任务`
  // 中文描述按实际字符计数，不强制填充到英文的最短字数。
  if ([...values.short_description].length < 2 || [...values.short_description].length > 64) throw new Error('short_description 必须为 2–64 个字符')
  return values
}

export const writeOpenaiYaml = async (directory: string, name: string, overrides: string[]) => {
  const values = interfaceValues(name, overrides)
  const file = join(directory, 'agents/openai.yaml')
  let existing: Record<string, unknown> = {}
  try {
    const parsed = Bun.YAML.parse(await readFile(file, 'utf8'))
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('openai.yaml 必须为映射')
    existing = parsed as Record<string, unknown>
  } catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error }
  // 窄修改：保留已有 policy、dependencies 和未指定的界面字段。
  const oldInterface = existing.interface && typeof existing.interface === 'object' ? existing.interface : {}
  const explicit = Object.fromEntries(overrides.map((entry) => [entry.slice(0, entry.indexOf('=')).trim(), entry.slice(entry.indexOf('=') + 1).trim()]))
  await mkdir(join(directory, 'agents'), { recursive: true })
  await writeFile(file, Bun.YAML.stringify({ ...existing, interface: { ...values, ...oldInterface, ...explicit } }, null, 2))
  return file
}

if (import.meta.main) {
  try {
    const { positionals, values } = parseArgs({ args: Bun.argv.slice(2), allowPositionals: true, options: { name: { type: 'string' }, interface: { type: 'string', multiple: true } } })
    if (positionals.length !== 1) throw new Error('用法：bun generate_openai_yaml.ts <skill_dir> [--name name] [--interface key=value]')
    const directory = resolve(positionals[0]!)
    const content = (await readFile(join(directory, 'SKILL.md'), 'utf8')).replace(/\r\n/g, '\n')
    const frontmatter = /^---\n([\s\S]*?)\n---/.exec(content)
    const meta = frontmatter ? Bun.YAML.parse(frontmatter[1]!) as Record<string, unknown> : {}
    const name = values.name ?? meta.name
    if (typeof name !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name)) throw new Error('缺少有效技能名称')
    console.log(await writeOpenaiYaml(directory, name, values.interface ?? []))
  } catch (error) { console.error(String(error)); process.exitCode = 1 }
}
