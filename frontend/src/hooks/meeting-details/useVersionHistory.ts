import { useCallback, useState } from 'react';
import { invoke as invokeTauri } from '@tauri-apps/api/core';
import { toast } from 'sonner';
import Analytics from '@/lib/analytics';
import type { VersionInfo, VersionKind } from '@/types/version';
import {
  defaultExportFormat,
  suggestExportFilename,
  type ExportFormat,
} from '@/lib/markdown-export';

const COMMANDS: Record<VersionKind, { list: string; render: string; restore: string }> = {
  transcript: {
    list: 'api_list_transcript_versions',
    render: 'api_render_transcript_version',
    restore: 'api_restore_transcript_version',
  },
  summary: {
    list: 'api_list_summary_versions',
    render: 'api_render_summary_version',
    restore: 'api_restore_summary_version',
  },
};

export function useVersionHistory(kind: VersionKind, meetingId: string, meetingTitle: string) {
  const [versions, setVersions] = useState<VersionInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const commands = COMMANDS[kind];

  const refresh = useCallback(async (): Promise<VersionInfo[]> => {
    setIsLoading(true);
    try {
      const rows = await invokeTauri<VersionInfo[]>(commands.list, { meetingId });
      setVersions(rows);
      return rows;
    } catch (error) {
      console.error(`Failed to list ${kind} versions:`, error);
      toast.error(`Failed to load ${kind} history`, {
        description: error instanceof Error ? error.message : String(error),
      });
      return [];
    } finally {
      setIsLoading(false);
    }
  }, [commands.list, kind, meetingId]);

  const render = useCallback(async (version: number): Promise<string> => {
    return invokeTauri<string>(commands.render, { meetingId, version });
  }, [commands.render, meetingId]);

  const exportVersion = useCallback(async (
    version: number,
    format: ExportFormat = defaultExportFormat(kind),
  ): Promise<void> => {
    try {
      const contents = await render(version);
      const base = suggestExportFilename(meetingTitle, kind, format).replace(/\.(md|txt)$/, '');
      const savedPath = await invokeTauri<string | null>('api_export_markdown', {
        suggestedFilename: `${base}-v${version}.${format}`,
        contents,
      });

      if (!savedPath) return;

      toast.success('Version exported', { description: savedPath });
      await Analytics.trackFeatureUsed(`export_${kind}_version_${format}`);
    } catch (error) {
      console.error(`Failed to export ${kind} version:`, error);
      toast.error('Failed to export version', {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  }, [kind, meetingTitle, render]);

  const restore = useCallback(async (version: number): Promise<boolean> => {
    try {
      await invokeTauri(commands.restore, { meetingId, version });
      await refresh();
      toast.success(`Restored ${kind} version ${version}`);
      await Analytics.trackFeatureUsed(`restore_${kind}_version`);
      return true;
    } catch (error) {
      console.error(`Failed to restore ${kind} version:`, error);
      toast.error('Failed to restore version', {
        description: error instanceof Error ? error.message : String(error),
      });
      return false;
    }
  }, [commands.restore, kind, meetingId, refresh]);

  return { versions, isLoading, refresh, render, exportVersion, restore };
}
