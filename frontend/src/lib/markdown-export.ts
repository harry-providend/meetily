import type { Block, Summary, Transcript } from '@/types';

/** Formats a recording-relative offset as [MM:SS], falling back to wall-clock for pre-audio-sync transcripts. */
export function formatTranscriptTime(
  seconds: number | undefined,
  fallbackTimestamp: string,
): string {
  if (seconds === undefined) {
    return fallbackTimestamp;
  }

  const totalSecs = Math.floor(seconds);
  const mins = Math.floor(totalSecs / 60);
  const secs = totalSecs % 60;
  return `[${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}]`;
}

function formatDateTime(value: string | number | Date): string {
  return new Date(value).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

interface TranscriptMarkdownOptions {
  meetingId: string;
  meetingTitle: string;
  createdAt: string;
  transcripts: Transcript[];
}

export function buildTranscriptMarkdown({
  meetingId,
  meetingTitle,
  createdAt,
  transcripts,
}: TranscriptMarkdownOptions): string {
  const header = `# Transcript of the Meeting: ${meetingId} - ${meetingTitle}\n\n`;
  const date = `## Date: ${new Date(createdAt).toLocaleDateString()}\n\n`;
  const body = transcripts
    // Two trailing spaces force a markdown line break between segments.
    .map((t) => `${formatTranscriptTime(t.audio_start_time, t.timestamp)} ${t.text}  `)
    .join('\n');

  return header + date + body;
}

interface SummaryMarkdownOptions {
  meetingId: string;
  meetingTitle: string;
  createdAt: string;
  body: string;
  /** Label for the second timestamp line, e.g. "Copied on" or "Exported on". */
  timestampLabel: string;
}

export function buildSummaryMarkdown({
  meetingId,
  meetingTitle,
  createdAt,
  body,
  timestampLabel,
}: SummaryMarkdownOptions): string {
  const header = `# Meeting Summary: ${meetingTitle}\n\n`;
  const metadata =
    `**Meeting ID:** ${meetingId}\n` +
    `**Date:** ${formatDateTime(createdAt)}\n` +
    `**${timestampLabel}:** ${formatDateTime(new Date())}\n\n---\n\n`;

  return header + metadata + body;
}

/** Keys on a Summary object that hold metadata rather than a renderable section. */
const NON_SECTION_KEYS = ['markdown', 'summary_json', '_section_order', 'MeetingName'];

/** Renders the pre-BlockNote summary shape, used when no markdown is stored. */
export function legacySummaryToMarkdown(summary: Summary): string {
  return Object.entries(summary)
    .filter(([key]) => !NON_SECTION_KEYS.includes(key))
    .map(([, section]) => {
      if (section && typeof section === 'object' && 'title' in section && 'blocks' in section) {
        const blocks = section.blocks.map((block: Block) => `- ${block.content}`).join('\n');
        return `## ${section.title}\n\n${blocks}`;
      }
      return '';
    })
    .filter((s) => s.trim())
    .join('\n\n');
}

/** Builds the filename offered in the save dialog. Rust sanitizes it before writing. */
export function suggestExportFilename(meetingTitle: string, kind: 'transcript' | 'summary'): string {
  const title = meetingTitle.trim() || 'meeting';
  return `${title}-${kind}.md`;
}
