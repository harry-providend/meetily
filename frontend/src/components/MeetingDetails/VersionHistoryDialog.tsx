"use client";

import { useCallback, useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Download, History, Loader2, RotateCcw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useVersionHistory } from '@/hooks/meeting-details/useVersionHistory';
import { describeReason, describeSize, type VersionKind } from '@/types/version';

interface VersionHistoryDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  kind: VersionKind;
  meetingId: string;
  meetingTitle: string;
  /** Called after a restore so the page can refetch the live copy. */
  onRestored?: () => Promise<void> | void;
}

export function VersionHistoryDialog({
  open,
  onOpenChange,
  kind,
  meetingId,
  meetingTitle,
  onRestored,
}: VersionHistoryDialogProps) {
  const { versions, isLoading, refresh, render, exportVersion, restore } =
    useVersionHistory(kind, meetingId, meetingTitle);

  const [selected, setSelected] = useState<number | null>(null);
  const [preview, setPreview] = useState<string>('');
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);

  useEffect(() => {
    if (!open) return;

    setSelected(null);
    setPreview('');
    void refresh().then((rows) => {
      if (rows.length > 0) setSelected(rows[0].version);
    });
  }, [open, refresh]);

  useEffect(() => {
    if (selected === null) return;

    let cancelled = false;
    setIsPreviewLoading(true);

    render(selected)
      .then((markdown) => {
        if (!cancelled) setPreview(markdown);
      })
      .catch((error) => {
        if (!cancelled) setPreview(`Failed to load preview: ${error}`);
      })
      .finally(() => {
        if (!cancelled) setIsPreviewLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selected, render]);

  const handleRestore = useCallback(async () => {
    if (selected === null) return;

    const warning = kind === 'transcript'
      ? `Restore transcript version ${selected}?\n\nThe current transcript is archived first, so this can be undone. The existing summary was generated from different text and will not be updated.`
      : `Restore summary version ${selected}?\n\nThe current summary is archived first, so this can be undone.`;

    if (!window.confirm(warning)) return;

    setIsRestoring(true);
    try {
      if (await restore(selected)) {
        await onRestored?.();
        onOpenChange(false);
      }
    } finally {
      setIsRestoring(false);
    }
  }, [kind, onOpenChange, onRestored, restore, selected]);

  const label = kind === 'transcript' ? 'Transcript' : 'Summary';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[70vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <History size={18} />
            {label} history
          </DialogTitle>
          <DialogDescription>
            Copies kept when something replaced the live {kind}. The 20 most recent
            are retained per meeting.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-1 gap-4 min-h-0">
          {/* Version list */}
          <div className="w-64 shrink-0 border rounded-md flex flex-col">
            <ScrollArea className="flex-1">
              {isLoading ? (
                <div className="p-4 text-sm text-gray-500 flex items-center gap-2">
                  <Loader2 className="animate-spin" size={14} /> Loading...
                </div>
              ) : versions.length === 0 ? (
                <div className="p-4 text-sm text-gray-500">
                  No earlier versions yet. One is saved whenever a
                  {kind === 'transcript' ? ' retranscription' : ' regeneration'} replaces
                  the current {kind}.
                </div>
              ) : (
                versions.map((v) => (
                  <button
                    key={v.version}
                    onClick={() => setSelected(v.version)}
                    className={`w-full text-left px-3 py-2 border-b last:border-b-0 hover:bg-gray-50 ${
                      selected === v.version ? 'bg-blue-50' : ''
                    }`}
                  >
                    <div className="font-medium text-sm">Version {v.version}</div>
                    <div className="text-xs text-gray-500">
                      {new Date(v.created_at).toLocaleString()}
                    </div>
                    <div className="text-xs text-gray-500">
                      {describeSize(kind, v.size)} · {describeReason(v.reason)}
                    </div>
                  </button>
                ))
              )}
            </ScrollArea>
          </div>

          {/* Preview */}
          <div className="flex-1 min-w-0 border rounded-md flex flex-col">
            <ScrollArea className="flex-1">
              {isPreviewLoading ? (
                <div className="p-4 text-sm text-gray-500 flex items-center gap-2">
                  <Loader2 className="animate-spin" size={14} /> Loading preview...
                </div>
              ) : !preview ? (
                <p className="p-4 text-xs text-gray-500">Select a version to preview it.</p>
              ) : kind === 'summary' ? (
                // Summaries are markdown; transcripts stay monospace so timestamps line up.
                <div className="prose prose-sm max-w-none p-4 break-words">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{preview}</ReactMarkdown>
                </div>
              ) : (
                <pre className="p-4 text-xs whitespace-pre-wrap break-words font-mono">
                  {preview}
                </pre>
              )}
            </ScrollArea>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2 border-t">
          {/* Transcripts export as plain text; summaries offer both from one trigger. */}
          {kind === 'summary' ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" disabled={selected === null}>
                  <Download size={16} />
                  Export
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  onClick={() => selected !== null && exportVersion(selected, 'md')}
                >
                  Export as .md
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => selected !== null && exportVersion(selected, 'txt')}
                >
                  Export as .txt
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Button
              variant="outline"
              size="sm"
              disabled={selected === null}
              onClick={() => selected !== null && exportVersion(selected, 'txt')}
            >
              <Download size={16} />
              Export
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            disabled={selected === null || isRestoring}
            onClick={handleRestore}
          >
            {isRestoring ? <Loader2 className="animate-spin" size={16} /> : <RotateCcw size={16} />}
            Restore
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
