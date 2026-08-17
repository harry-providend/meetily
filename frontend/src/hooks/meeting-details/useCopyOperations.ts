import { useCallback, RefObject } from 'react';
import { Transcript, Summary } from '@/types';
import { BlockNoteSummaryViewRef } from '@/components/AISummary/BlockNoteSummaryView';
import { toast } from 'sonner';
import { invoke as invokeTauri } from '@tauri-apps/api/core';
import {
  buildSummaryMarkdown,
  buildTranscriptMarkdown,
  legacySummaryToMarkdown,
  suggestExportFilename,
  type ExportFormat,
} from '@/lib/markdown-export';

interface TranscriptMarkdown {
  markdown: string;
  segmentCount: number;
  wordCount: number;
}

interface UseCopyOperationsProps {
  meeting: any;
  transcripts: Transcript[];
  meetingTitle: string;
  aiSummary: Summary | null;
  blockNoteSummaryRef: RefObject<BlockNoteSummaryViewRef>;
}

export function useCopyOperations({
  meeting,
  transcripts,
  meetingTitle,
  aiSummary,
  blockNoteSummaryRef,
}: UseCopyOperationsProps) {

  // Helper function to fetch ALL transcripts for copying (not just paginated data)
  const fetchAllTranscripts = useCallback(async (meetingId: string): Promise<Transcript[]> => {
    try {
      console.log('📊 Fetching all transcripts for copying:', meetingId);

      // First, get total count by fetching first page
      const firstPage = await invokeTauri('api_get_meeting_transcripts', {
        meetingId,
        limit: 1,
        offset: 0,
      }) as { transcripts: Transcript[]; total_count: number; has_more: boolean };

      const totalCount = firstPage.total_count;
      console.log(`📊 Total transcripts in database: ${totalCount}`);

      if (totalCount === 0) {
        return [];
      }

      // Fetch all transcripts in one call
      const allData = await invokeTauri('api_get_meeting_transcripts', {
        meetingId,
        limit: totalCount,
        offset: 0,
      }) as { transcripts: Transcript[]; total_count: number; has_more: boolean };

      console.log(`✅ Fetched ${allData.transcripts.length} transcripts from database for copying`);
      return allData.transcripts;
    } catch (error) {
      console.error('❌ Error fetching all transcripts:', error);
      toast.error('Failed to fetch transcripts for copying');
      return [];
    }
  }, []);

  // Builds the full transcript markdown, or null when the meeting has no segments
  const resolveTranscriptMarkdown = useCallback(async (): Promise<TranscriptMarkdown | null> => {
    const allTranscripts = await fetchAllTranscripts(meeting.id);

    if (!allTranscripts.length) {
      toast.error('No transcripts available');
      return null;
    }

    return {
      markdown: buildTranscriptMarkdown({
        meetingId: meeting.id,
        meetingTitle: meetingTitle ?? meeting.title,
        createdAt: meeting.created_at,
        transcripts: allTranscripts,
      }),
      segmentCount: allTranscripts.length,
      wordCount: allTranscripts
        .map(t => t.text.split(/\s+/).length)
        .reduce((a, b) => a + b, 0),
    };
  }, [meeting, meetingTitle, fetchAllTranscripts]);

  // Reads the live editor first so unsaved edits are included, then falls back to stored formats
  const resolveSummaryMarkdown = useCallback(async (): Promise<string | null> => {
    let summaryMarkdown = '';

    if (blockNoteSummaryRef.current?.getMarkdown) {
      summaryMarkdown = await blockNoteSummaryRef.current.getMarkdown();
    }

    if (!summaryMarkdown && aiSummary && 'markdown' in aiSummary) {
      summaryMarkdown = (aiSummary as any).markdown || '';
    }

    if (!summaryMarkdown && aiSummary) {
      summaryMarkdown = legacySummaryToMarkdown(aiSummary);
    }

    if (!summaryMarkdown.trim()) {
      toast.error('No summary content available');
      return null;
    }

    return summaryMarkdown;
  }, [aiSummary, blockNoteSummaryRef]);

  // Opens the native save dialog. Resolves to false when the user cancels.
  const exportMarkdown = useCallback(async (
    kind: 'transcript' | 'summary',
    contents: string,
    format?: ExportFormat,
  ): Promise<boolean> => {
    const savedPath = await invokeTauri<string | null>('api_export_markdown', {
      suggestedFilename: suggestExportFilename(meetingTitle ?? meeting.title, kind, format),
      contents,
    });

    if (!savedPath) return false;

    toast.success(`${kind === 'transcript' ? 'Transcript' : 'Summary'} exported`, {
      description: savedPath,
    });
    return true;
  }, [meeting, meetingTitle]);

  const handleExportTranscript = useCallback(async () => {
    try {
      const resolved = await resolveTranscriptMarkdown();
      if (!resolved) return;

      await exportMarkdown('transcript', resolved.markdown);
    } catch (error) {
      console.error('❌ Failed to export transcript:', error);
      toast.error('Failed to export transcript', {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  }, [resolveTranscriptMarkdown, exportMarkdown]);

  const handleExportSummary = useCallback(async (format: ExportFormat = 'md') => {
    try {
      const body = await resolveSummaryMarkdown();
      if (body === null) return;

      await exportMarkdown('summary', buildSummaryMarkdown({
        meetingId: meeting.id,
        meetingTitle,
        createdAt: meeting.created_at,
        body,
        timestampLabel: 'Exported on',
      }), format);
    } catch (error) {
      console.error('❌ Failed to export summary:', error);
      toast.error('Failed to export summary', {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  }, [meeting, meetingTitle, resolveSummaryMarkdown, exportMarkdown]);

  return {
    handleExportTranscript,
    handleExportSummary,
  };
}
