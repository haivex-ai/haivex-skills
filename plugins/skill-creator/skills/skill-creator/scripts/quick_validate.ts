// Adapted from OpenAI skill-creator (Apache-2.0); Haivex TypeScript/Bun port.
import { readFile } from 'node:fs/promises'
import { basename, join, resolve } from 'node:path'

export const validateSkill = async (directory: string) => {
  try {
    const content = (await readFile(join(directory, 'SKILL.md'), 'utf8')).replace(/^\uFEFF/, '').replace(/\r\n/g, '\n')
    const match = /^---\n([\s\S]*?)\n---(?:\n|$)/.exec(content)
    if (!match) throw new Error('SKILL.md 缺少 YAML 元数据')
    const meta = Bun.YAML.parse(match[1]!) as Record<string, unknown>
    if (!meta || typeof meta !== 'object' || Array.isArray(meta)) throw new Error('元数据必须为映射')
    const allowed = new Set(['name', 'description', 'license', 'allowed-tools', 'metadata'])
    if (Object.keys(meta).some((key) => !allowed.has(key))) throw new Error('元数据含不支持的字段')
    if (typeof meta.name !== 'string' || meta.name.length > 64 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(meta.name)) throw new Error('name 必须为 1–64 位小写英文、数字和单连字符')
    if (meta.name !== basename(resolve(directory))) throw new Error('目录名必须与 name 一致')
    if (typeof meta.description !== 'string' || !meta.description.trim() || meta.description.length > 1024 || /[<>]/.test(meta.description) || meta.description.startsWith('[TODO:')) throw new Error('description 为空、过长、包含尖括号或尚未完成')
    const body = content.slice(match[0].length)
    if (!body.trim()) throw new Error('技能正文为空')
    let fence: { marker: string; length: number } | null = null
    for (const line of body.split('\n')) {
      const marker = /^[ \t]*(?:(?:[-+*]|\d+[.)])[ \t]+)?(`{3,}|~{3,})(.*)$/.exec(line)
      if (marker) {
        if (!fence) fence = { marker: marker[1]![0]!, length: marker[1]!.length }
        else if (fence.marker === marker[1]![0] && marker[1]!.length >= fence.length && !marker[2]!.trim()) fence = null
      } else if (!fence && /^[ ]{0,3}\[TODO:[^\n]*\][ \t]*$/.test(line)) throw new Error('技能正文尚有未完成占位符')
    }
    return { valid: true, message: '技能格式有效；仍需用真实任务验证执行效果。' }
  } catch (error) { return { valid: false, message: String(error) } }
}

if (import.meta.main) {
  const result = Bun.argv.length === 3 ? await validateSkill(resolve(Bun.argv[2]!)) : { valid: false, message: '用法：bun quick_validate.ts <skill_directory>' }
  console.log(result.message)
  process.exitCode = result.valid ? 0 : 1
}
