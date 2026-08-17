/** Which history a version belongs to. */
export type VersionKind = 'transcript' | 'summary';

/** Row returned by `api_list_transcript_versions` / `api_list_summary_versions`. */
export interface VersionInfo {
  version: number;
  /** What caused the snapshot: 'retranscription', 'regeneration' or 'restore'. */
  reason: string;
  created_at: string;
  /** Segment count for transcripts, word count for summaries. */
  size: number;
}

const REASON_LABELS: Record<string, string> = {
  retranscription: 'Replaced by retranscription',
  regeneration: 'Replaced by regeneration',
  restore: 'Replaced by a restore',
};

export function describeReason(reason: string): string {
  return REASON_LABELS[reason] ?? reason;
}

export function describeSize(kind: VersionKind, size: number): string {
  return kind === 'transcript'
    ? `${size} segment${size === 1 ? '' : 's'}`
    : `${size} word${size === 1 ? '' : 's'}`;
}
