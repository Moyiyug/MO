/** 前端基础校验 — 最终以后端 validators 为准 */

const GITHUB_REPO_RE =
  /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(\/tree\/[A-Za-z0-9_.-]+(\/[A-Za-z0-9_.-]+)*)?$/

export function isValidRepoUrl(url: string): boolean {
  return GITHUB_REPO_RE.test(url.trim())
}

export function parseRepoUrls(text: string): string[] {
  return text
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

export function validateRepoUrlList(urls: string[]): string | null {
  // F-015：repo_urls 可选（0-5）。留空时由 RepoDiscovery 自动发现。
  if (urls.length > 5) return '最多 5 个仓库 URL'
  for (const u of urls) {
    if (!isValidRepoUrl(u)) {
      return `无效的 GitHub 仓库 URL：${u}`
    }
  }
  return null
}
