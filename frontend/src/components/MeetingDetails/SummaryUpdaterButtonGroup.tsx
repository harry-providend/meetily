"use client";

import { Button } from '@/components/ui/button';
import { ButtonGroup } from '@/components/ui/button-group';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Download, History, Save, Loader2, Search, FolderOpen } from 'lucide-react';
import type { ExportFormat } from '@/lib/markdown-export';

interface SummaryUpdaterButtonGroupProps {
  isSaving: boolean;
  isDirty: boolean;
  onSave: () => Promise<void>;
  onExport: (format: ExportFormat) => Promise<void>;
  onOpenVersionHistory: () => void;
  onFind?: () => void;
  onOpenFolder: () => Promise<void>;
  hasSummary: boolean;
}

export function SummaryUpdaterButtonGroup({
  isSaving,
  isDirty,
  onSave,
  onExport,
  onOpenVersionHistory,
  onFind,
  onOpenFolder,
  hasSummary
}: SummaryUpdaterButtonGroupProps) {
  return (
    <ButtonGroup>
      {/* Save button */}
      <Button
        variant="outline"
        size="sm"
        className={`${isDirty ? 'bg-green-200' : ""}`}
        title={isSaving ? "Saving" : "Save Changes"}
        onClick={() => {
          onSave();
        }}
        disabled={isSaving}
      >
        {isSaving ? (
          <>
            <Loader2 className="animate-spin" />
            <span className="hidden lg:inline">Saving...</span>
          </>
        ) : (
          <>
            <Save />
            <span className="hidden lg:inline">Save</span>
          </>
        )}
      </Button>

      {/* Export button — one trigger, format chosen from the menu */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            title="Export Summary"
            disabled={!hasSummary}
            className="cursor-pointer"
          >
            <Download />
            <span className="hidden lg:inline">Export</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onClick={() => {
              onExport('md');
            }}
          >
            Export as .md
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => {
              onExport('txt');
            }}
          >
            Export as .txt
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* History button */}
      <Button
        variant="outline"
        size="sm"
        title="Summary version history"
        onClick={() => {
          onOpenVersionHistory();
        }}
        className="cursor-pointer"
      >
        <History />
        <span className="hidden lg:inline">History</span>
      </Button>

      {/* Find button */}
      {/* {onFind && (
        <Button
          variant="outline"
          size="sm"
          title="Find in Summary"
          onClick={() => {
            onFind();
          }}
          disabled={!hasSummary}
          className="cursor-pointer"
        >
          <Search />
          <span className="hidden lg:inline">Find</span>
        </Button>
      )} */}
    </ButtonGroup>
  );
}
