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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  ArrowDown,
  ArrowUp,
  Loader2,
  Lock,
  Plus,
  RotateCcw,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  createEmptySection,
  createEmptyTemplate,
  TEMPLATE_SECTION_FORMATS,
  validateTemplate,
  type SaveTemplateRequest,
  type TemplateDetails,
  type TemplateInfo,
  type TemplateSectionFormat,
} from '@/types/template';

interface TemplateManagerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  templates: TemplateInfo[];
  getTemplateDetails: (templateId: string) => Promise<TemplateDetails>;
  saveTemplate: (request: SaveTemplateRequest) => Promise<string>;
  deleteTemplate: (templateId: string) => Promise<void>;
  resetTemplate: (templateId: string) => Promise<void>;
  /** Id to open the editor on. Falls back to the first template. */
  initialTemplateId?: string;
}

export function TemplateManagerDialog({
  open,
  onOpenChange,
  templates,
  getTemplateDetails,
  saveTemplate,
  deleteTemplate,
  resetTemplate,
  initialTemplateId,
}: TemplateManagerDialogProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<TemplateDetails | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  // Composing a new template that has no row yet
  const [isCreating, setIsCreating] = useState(false);

  const loadTemplate = useCallback(async (templateId: string) => {
    setIsLoading(true);
    try {
      const details = await getTemplateDetails(templateId);
      setDraft(details);
      setSelectedId(templateId);
      setIsCreating(false);
      setIsDirty(false);
    } catch (error) {
      console.error('Failed to load template:', error);
      toast.error('Failed to load template', {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setIsLoading(false);
    }
  }, [getTemplateDetails]);

  // Open on the requested template, or the first available
  useEffect(() => {
    if (!open) return;
    const target = initialTemplateId && templates.some((t) => t.id === initialTemplateId)
      ? initialTemplateId
      : templates[0]?.id;
    if (target) {
      void loadTemplate(target);
    } else {
      setDraft(createEmptyTemplate());
      setIsCreating(true);
    }
    // Only re-run on open, so a save does not discard editor state
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const confirmDiscard = useCallback(() => {
    if (!isDirty) return true;
    return window.confirm('Discard unsaved changes to this template?');
  }, [isDirty]);

  const handleSelect = (templateId: string) => {
    if (templateId === selectedId && !isCreating) return;
    if (!confirmDiscard()) return;
    void loadTemplate(templateId);
  };

  const handleNew = () => {
    if (!confirmDiscard()) return;
    setDraft(createEmptyTemplate());
    setSelectedId(null);
    setIsCreating(true);
    setIsDirty(false);
  };

  const updateDraft = (patch: Partial<TemplateDetails>) => {
    setDraft((current) => (current ? { ...current, ...patch } : current));
    setIsDirty(true);
  };

  const updateSection = (index: number, patch: Partial<TemplateDetails['sections'][number]>) => {
    setDraft((current) => {
      if (!current) return current;
      const sections = current.sections.map((section, i) =>
        i === index ? { ...section, ...patch } : section
      );
      return { ...current, sections };
    });
    setIsDirty(true);
  };

  const addSection = () => {
    setDraft((current) =>
      current ? { ...current, sections: [...current.sections, createEmptySection()] } : current
    );
    setIsDirty(true);
  };

  const removeSection = (index: number) => {
    setDraft((current) => {
      if (!current) return current;
      return { ...current, sections: current.sections.filter((_, i) => i !== index) };
    });
    setIsDirty(true);
  };

  const moveSection = (index: number, direction: -1 | 1) => {
    setDraft((current) => {
      if (!current) return current;
      const target = index + direction;
      if (target < 0 || target >= current.sections.length) return current;
      const sections = [...current.sections];
      [sections[index], sections[target]] = [sections[target], sections[index]];
      return { ...current, sections };
    });
    setIsDirty(true);
  };

  const handleSave = async () => {
    if (!draft) return;

    const validationError = validateTemplate(draft);
    if (validationError) {
      toast.error('Template is incomplete', { description: validationError });
      return;
    }

    setIsSaving(true);
    try {
      const savedId = await saveTemplate({
        // Omitting the id creates a new template
        id: isCreating ? undefined : draft.id,
        name: draft.name.trim(),
        description: draft.description.trim(),
        sections: draft.sections.map((section) => ({
          ...section,
          title: section.title.trim(),
          instruction: section.instruction.trim(),
          // Drop empty hints rather than storing blank strings
          item_format: section.item_format?.trim() || undefined,
          example_item_format: section.example_item_format?.trim() || undefined,
        })),
      });

      toast.success(isCreating ? 'Template created' : 'Template saved');
      setIsDirty(false);
      await loadTemplate(savedId);
    } catch (error) {
      console.error('Failed to save template:', error);
      toast.error('Failed to save template', {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!draft || isCreating) return;
    if (!window.confirm(`Delete the template "${draft.name}"? This cannot be undone.`)) return;

    try {
      await deleteTemplate(draft.id);
      toast.success('Template deleted');
      setIsDirty(false);

      const remaining = templates.filter((t) => t.id !== draft.id);
      if (remaining.length > 0) {
        await loadTemplate(remaining[0].id);
      } else {
        setDraft(createEmptyTemplate());
        setSelectedId(null);
        setIsCreating(true);
      }
    } catch (error) {
      console.error('Failed to delete template:', error);
      toast.error('Failed to delete template', {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const handleReset = async () => {
    if (!draft || isCreating) return;
    if (!window.confirm(`Reset "${draft.name}" to the version shipped with the app?`)) return;

    try {
      await resetTemplate(draft.id);
      toast.success('Template reset to default');
      setIsDirty(false);
      await loadTemplate(draft.id);
    } catch (error) {
      console.error('Failed to reset template:', error);
      toast.error('Failed to reset template', {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && !confirmDiscard()) return;
    onOpenChange(nextOpen);
  };

  const canDelete = !isCreating && draft !== null && !draft.is_builtin;
  const canReset = !isCreating && draft !== null && draft.is_builtin && draft.user_modified;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>Manage summary templates</DialogTitle>
          <DialogDescription>
            Templates control the sections the AI produces and the instructions it follows for each one.
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-4 min-h-0 max-h-[65vh]">
          {/* Template list */}
          <div className="w-56 flex-shrink-0 flex flex-col gap-2 border-r border-gray-200 pr-3">
            <Button variant="outline" size="sm" onClick={handleNew} className="justify-start">
              <Plus size={16} className="mr-2" />
              New template
            </Button>

            <div className="flex-1 overflow-y-auto space-y-1">
              {templates.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => handleSelect(template.id)}
                  className={`w-full text-left px-2 py-1.5 rounded text-sm hover:bg-gray-100 ${
                    selectedId === template.id && !isCreating ? 'bg-gray-100 font-medium' : ''
                  }`}
                  title={template.description}
                >
                  <span className="flex items-center gap-1.5">
                    <span className="truncate">{template.name}</span>
                    {template.is_builtin && (
                      <Lock size={12} className="text-gray-400 flex-shrink-0" aria-label="Built-in" />
                    )}
                  </span>
                </button>
              ))}
              {isCreating && (
                <div className="px-2 py-1.5 rounded text-sm bg-blue-50 font-medium text-blue-700">
                  {draft?.name.trim() || 'Untitled template'}
                </div>
              )}
            </div>
          </div>

          {/* Editor */}
          <div className="flex-1 min-w-0 overflow-y-auto pr-1">
            {isLoading ? (
              <div className="flex items-center justify-center h-40 text-gray-500">
                <Loader2 className="animate-spin mr-2" size={18} />
                Loading template...
              </div>
            ) : draft ? (
              <div className="space-y-4">
                {draft.is_builtin && (
                  <p className="text-xs text-gray-500 bg-gray-50 rounded px-3 py-2">
                    This template ships with the app. Your edits are kept across app updates, and
                    you can restore the original at any time.
                  </p>
                )}

                <div className="space-y-2">
                  <Label htmlFor="template-name">Name</Label>
                  <Input
                    id="template-name"
                    value={draft.name}
                    onChange={(e) => updateDraft({ name: e.target.value })}
                    placeholder="Weekly Sync"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="template-description">Description</Label>
                  <Input
                    id="template-description"
                    value={draft.description}
                    onChange={(e) => updateDraft({ description: e.target.value })}
                    placeholder="What this template is for"
                  />
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label>Sections</Label>
                    <Button variant="outline" size="sm" onClick={addSection}>
                      <Plus size={14} className="mr-1" />
                      Add section
                    </Button>
                  </div>

                  {draft.sections.map((section, index) => (
                    <div key={index} className="border border-gray-200 rounded-md p-3 space-y-2">
                      <div className="flex items-center gap-2">
                        <Input
                          value={section.title}
                          onChange={(e) => updateSection(index, { title: e.target.value })}
                          placeholder="Section title"
                          className="flex-1"
                        />
                        <Select
                          value={section.format}
                          onValueChange={(value) =>
                            updateSection(index, { format: value as TemplateSectionFormat })
                          }
                        >
                          <SelectTrigger className="w-32">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {TEMPLATE_SECTION_FORMATS.map((format) => (
                              <SelectItem key={format} value={format}>
                                {format}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => moveSection(index, -1)}
                          disabled={index === 0}
                          title="Move up"
                        >
                          <ArrowUp size={14} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => moveSection(index, 1)}
                          disabled={index === draft.sections.length - 1}
                          title="Move down"
                        >
                          <ArrowDown size={14} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeSection(index)}
                          disabled={draft.sections.length === 1}
                          title="Remove section"
                        >
                          <Trash2 size={14} className="text-red-500" />
                        </Button>
                      </div>

                      <Textarea
                        value={section.instruction}
                        onChange={(e) => updateSection(index, { instruction: e.target.value })}
                        placeholder="What the AI should extract for this section"
                        rows={2}
                      />

                      {section.format === 'list' && (
                        <Input
                          value={section.item_format ?? ''}
                          onChange={(e) => updateSection(index, { item_format: e.target.value })}
                          placeholder="Optional item format, e.g. | Owner | Task | Due |"
                          className="font-mono text-xs"
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-40 text-gray-500 text-sm">
                Select a template to edit, or create a new one.
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-gray-200 pt-3">
          <div className="flex gap-2">
            {canDelete && (
              <Button variant="outline" size="sm" onClick={handleDelete}>
                <Trash2 size={14} className="mr-1 text-red-500" />
                Delete
              </Button>
            )}
            {canReset && (
              <Button variant="outline" size="sm" onClick={handleReset}>
                <RotateCcw size={14} className="mr-1" />
                Reset to default
              </Button>
            )}
          </div>

          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => handleOpenChange(false)}>
              Close
            </Button>
            <Button size="sm" onClick={handleSave} disabled={isSaving || !draft || !isDirty}>
              {isSaving ? (
                <>
                  <Loader2 className="animate-spin mr-2" size={14} />
                  Saving...
                </>
              ) : (
                'Save template'
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
