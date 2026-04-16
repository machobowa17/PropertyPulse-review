/**
 * schemas/area.ts — Zod schemas for the /area API response boundary.
 *
 * R8: validate `details` payload so malformed API responses surface early
 * rather than silently rendering blank MetricCard expanded panels.
 *
 * We validate structural correctness only — field-level ranges and units
 * are the backend's responsibility. The goal is to catch null-where-object,
 * unexpected primitives, and completely missing required fields.
 */
import { z } from 'zod';

// ── Sub-object schemas ─────────────────────────────────────────────────────

const MetricMapBindingSchema = z.object({
  layer: z.string(),
  label: z.string().optional(),
});

const MetricRegistryMetaSchema = z.object({
  short_label: z.string(),
  section_id: z.string().optional().nullable(),
  value_type: z.string().optional().nullable(),
});

const MetricHeadlineSchema = z.object({
  formatted: z.string().nullable(),
  parent_formatted: z.string().nullable().optional(),
});

const MetricComparisonSchema = z.object({
  flag: z.string().nullable(),
  status: z.string(),
});

const MetricTrendSchema = z.object({
  status: z.string(),
  direction: z.string().nullable().optional(),
  value: z.number().nullable().optional(),
});

const MetricCapsuleSchema = z.object({
  label: z.string(),
  colour: z.string(),
}).nullable();

// ── Metric schema — details is loosely typed (Record<string, unknown>) ─────

export const MetricSchema = z.object({
  id: z.string(),
  name: z.string(),
  local_value: z.union([z.number(), z.string()]).nullable(),
  parent_value: z.union([z.number(), z.string()]).nullable(),
  unit: z.string(),
  comparison_flag: z.string().nullable(),
  comparison_status: z.string(),
  trend_status: z.string(),
  map_binding: z.union([z.string(), MetricMapBindingSchema]).nullable().optional(),
  decision_question: z.string().nullable().optional(),
  interpretation_direction: z.string().nullable().optional(),
  quality_notes: z.string().nullable().optional(),
  // details: validated as null or plain object — no deeper structural check needed here
  // (the MetricCard's num/str/arr/rec helpers handle field-level safety)
  details: z.record(z.string(), z.unknown()).nullable().optional(),
  // Nested sub-objects from build_metric_contract()
  registry: MetricRegistryMetaSchema,
  headline: MetricHeadlineSchema,
  comparison: MetricComparisonSchema,
  trend: MetricTrendSchema,
  capsule: MetricCapsuleSchema.optional(),
  quality_flags: z.array(z.string()).optional(),
});

export const AreaResponseSchema = z.object({
  tab: z.string(),
  metrics: z.array(MetricSchema),
});

export type ValidatedMetric = z.infer<typeof MetricSchema>;
export type ValidatedAreaResponse = z.infer<typeof AreaResponseSchema>;
