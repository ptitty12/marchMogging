export interface LevelDef {
  key: string
  label: string
}

export interface ForecastConfig {
  id: number
  business_unit_id: number
  name: string
  active: boolean
  levels: LevelDef[]
  metric_rules: { default: string; overrides: MetricOverride[] }
  pipeline_weighting: { mode: string; rate?: number }
  fact_filters: Record<string, string[]> | null
  bucket_rollups: Record<string, string[]> | null
  source_orders_view: string | null
  source_pipeline_view: string | null
}

export interface MetricOverride {
  field: string
  equals: string
  metric: string
}

export interface BusinessUnit {
  id: number
  code: string
  name: string
  description: string | null
  configs: ForecastConfig[]
}

export interface Period {
  code: string
  year: number
  quarter: number
  start_date: string
  end_date: string
}

export interface Dimension {
  key: string
  label: string
  derived: boolean
  description: string | null
}

export interface GridRow {
  period_code: string
  slice_key: string
  slice_values: Record<string, string>
  actuals: number
  pipeline_open: number
  pipeline_weighted: number
  suggested_all_bfo: number
  suggested_buildup: number
  adjustment: number | null
  total_forecast: number | null
  effective_adjustment: number
  effective_total: number
  comment: string | null
  updated_by: string | null
  updated_at: string | null
  has_entry: boolean
}

export interface Grid {
  config: ForecastConfig
  periods: string[]
  rows: GridRow[]
}

export interface AuditRecord {
  id: number
  config_id: number
  period_code: string
  slice_key: string
  field: string
  old_value: string | null
  new_value: string | null
  changed_by: string
  changed_at: string
}
