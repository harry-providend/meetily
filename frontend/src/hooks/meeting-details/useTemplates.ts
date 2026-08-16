import { useState, useEffect, useCallback } from 'react';
import { invoke as invokeTauri } from '@tauri-apps/api/core';
import { toast } from 'sonner';
import Analytics from '@/lib/analytics';
import type {
  SaveTemplateRequest,
  TemplateDetails,
  TemplateInfo,
} from '@/types/template';

const DEFAULT_TEMPLATE_ID = 'standard_meeting';

export function useTemplates() {
  const [availableTemplates, setAvailableTemplates] = useState<TemplateInfo[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>(DEFAULT_TEMPLATE_ID);

  const refreshTemplates = useCallback(async (): Promise<TemplateInfo[]> => {
    try {
      const templates = await invokeTauri<TemplateInfo[]>('api_list_templates');
      setAvailableTemplates(templates);

      // Fall back if the selected template was deleted
      setSelectedTemplate((current) => {
        if (templates.some((t) => t.id === current)) return current;
        return templates.find((t) => t.id === DEFAULT_TEMPLATE_ID)?.id
          ?? templates[0]?.id
          ?? DEFAULT_TEMPLATE_ID;
      });

      return templates;
    } catch (error) {
      console.error('Failed to fetch templates:', error);
      toast.error('Failed to load templates', {
        description: error instanceof Error ? error.message : String(error),
      });
      return [];
    }
  }, []);

  useEffect(() => {
    void refreshTemplates();
  }, [refreshTemplates]);

  const handleTemplateSelection = useCallback((templateId: string, templateName: string) => {
    setSelectedTemplate(templateId);
    toast.success('Template selected', {
      description: `Using "${templateName}" template for summary generation`,
    });
    Analytics.trackFeatureUsed('template_selected');
  }, []);

  /** Loads the full definition of a template for editing. */
  const getTemplateDetails = useCallback(async (templateId: string): Promise<TemplateDetails> => {
    return invokeTauri<TemplateDetails>('api_get_template_details', { templateId });
  }, []);

  /** Creates or updates a template. Returns the saved template's id. */
  const saveTemplate = useCallback(async (request: SaveTemplateRequest): Promise<string> => {
    const savedId = await invokeTauri<string>('api_save_template', { request });
    await refreshTemplates();
    Analytics.trackFeatureUsed(request.id ? 'template_updated' : 'template_created');
    return savedId;
  }, [refreshTemplates]);

  const deleteTemplate = useCallback(async (templateId: string): Promise<void> => {
    await invokeTauri('api_delete_template', { templateId });
    await refreshTemplates();
    Analytics.trackFeatureUsed('template_deleted');
  }, [refreshTemplates]);

  /** Restores a built-in template to the definition shipped with the app. */
  const resetTemplate = useCallback(async (templateId: string): Promise<void> => {
    await invokeTauri('api_reset_template', { templateId });
    await refreshTemplates();
    Analytics.trackFeatureUsed('template_reset');
  }, [refreshTemplates]);

  return {
    availableTemplates,
    selectedTemplate,
    handleTemplateSelection,
    refreshTemplates,
    getTemplateDetails,
    saveTemplate,
    deleteTemplate,
    resetTemplate,
  };
}
