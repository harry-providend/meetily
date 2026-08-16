/** Section format understood by the summary generator. */
export type TemplateSectionFormat = 'paragraph' | 'list' | 'string';

export const TEMPLATE_SECTION_FORMATS: TemplateSectionFormat[] = [
  'paragraph',
  'list',
  'string',
];

export interface TemplateSection {
  /** Section heading, e.g. "Action Items" */
  title: string;
  /** Instruction handed to the LLM for this section */
  instruction: string;
  format: TemplateSectionFormat;
  /** Optional markdown hint for list items, e.g. a table row layout */
  item_format?: string;
  example_item_format?: string;
}

/** Row returned by `api_list_templates`. */
export interface TemplateInfo {
  id: string;
  name: string;
  description: string;
  /** Ships with the app: editable and resettable, but not deletable. */
  is_builtin: boolean;
  /** A built-in the user has edited, so "Reset to default" applies. */
  user_modified: boolean;
  updated_at: string;
}

/** Full definition returned by `api_get_template_details`. */
export interface TemplateDetails {
  id: string;
  name: string;
  description: string;
  sections: TemplateSection[];
  is_builtin: boolean;
  user_modified: boolean;
}

/** Payload accepted by `api_save_template`. Omit `id` to create. */
export interface SaveTemplateRequest {
  id?: string;
  name: string;
  description: string;
  sections: TemplateSection[];
}

export function createEmptySection(): TemplateSection {
  return {
    title: '',
    instruction: '',
    format: 'list',
  };
}

export function createEmptyTemplate(): TemplateDetails {
  return {
    id: '',
    name: '',
    description: '',
    sections: [createEmptySection()],
    is_builtin: false,
    user_modified: false,
  };
}

/** Mirrors `Template::validate` in Rust so the editor can report errors inline. */
export function validateTemplate(template: TemplateDetails): string | null {
  if (!template.name.trim()) return 'Template name cannot be empty';
  if (!template.description.trim()) return 'Template description cannot be empty';
  if (template.sections.length === 0) return 'Template must have at least one section';

  for (const [index, section] of template.sections.entries()) {
    if (!section.title.trim()) return `Section ${index + 1} needs a title`;
    if (!section.instruction.trim()) {
      return `Section "${section.title.trim() || index + 1}" needs an instruction`;
    }
  }

  return null;
}
