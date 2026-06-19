import type { EvidenceItem } from '@/types/evidence'

export interface EvidenceLookup {
  byId: Map<string, EvidenceItem>
  labelById: Map<string, string>
}

export function buildEvidenceLookup(items: EvidenceItem[] | undefined): EvidenceLookup {
  const byId = new Map<string, EvidenceItem>()
  const labelById = new Map<string, string>()

  for (const [index, item] of (items ?? []).entries()) {
    byId.set(item.id, item)
    labelById.set(item.id, `E${index + 1}`)
  }

  return { byId, labelById }
}

export function getEvidenceLabel(evidenceId: string, lookup: EvidenceLookup): string {
  return lookup.labelById.get(evidenceId) ?? evidenceId
}

export function isExternalEvidenceSource(uri: string): boolean {
  return /^https?:\/\//i.test(uri)
}
