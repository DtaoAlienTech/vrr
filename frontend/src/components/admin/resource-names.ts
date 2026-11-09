// The staff screens that are plain lists + editors (see resources.tsx for what each one is).
export const RESOURCE_NAMES = ["news", "activities", "gallery", "departments", "courses", "faculty"] as const;
export type ResourceName = (typeof RESOURCE_NAMES)[number];

export const isResourceName = (value: string): value is ResourceName => (RESOURCE_NAMES as readonly string[]).includes(value);
