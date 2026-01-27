import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Convert American odds to decimal odds
 */
export function americanToDecimal(american: number): number {
  if (american > 0) {
    return american / 100 + 1
  }
  return 100 / Math.abs(american) + 1
}

/**
 * Convert decimal odds to American odds
 */
export function decimalToAmerican(decimal: number): number {
  if (decimal >= 2) {
    return Math.round((decimal - 1) * 100)
  }
  return Math.round(-100 / (decimal - 1))
}

/**
 * Calculate implied probability from American odds
 */
export function impliedProbability(american: number): number {
  if (american > 0) {
    return 100 / (american + 100)
  }
  return Math.abs(american) / (Math.abs(american) + 100)
}

/**
 * Format American odds with sign
 */
export function formatOdds(american: number): string {
  if (american > 0) {
    return `+${american}`
  }
  return american.toString()
}

/**
 * Format percentage
 */
export function formatPercent(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`
}

/**
 * Format currency
 */
export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

/**
 * Format edge as percentage with color indicator
 */
export function formatEdge(edge: number): { text: string; className: string } {
  const text = `${edge >= 0 ? '+' : ''}${(edge * 100).toFixed(1)}%`
  const className = edge > 0 ? 'value-positive' : edge < 0 ? 'value-negative' : 'value-neutral'
  return { text, className }
}

/**
 * Calculate Kelly stake percentage
 */
export function kellyStake(probability: number, decimalOdds: number, fraction = 0.25): number {
  const b = decimalOdds - 1
  const q = 1 - probability
  const kelly = (b * probability - q) / b
  return Math.max(0, kelly * fraction)
}

/**
 * Get sport display name
 */
export function sportDisplayName(sport: string): string {
  const names: Record<string, string> = {
    nfl: 'NFL',
    nba: 'NBA',
    mlb: 'MLB',
    soccer: 'Soccer',
    ncaaf: 'NCAAF',
    ncaab: 'NCAAB',
  }
  return names[sport] || sport.toUpperCase()
}

/**
 * Get sport color
 */
export function sportColor(sport: string): string {
  const colors: Record<string, string> = {
    nfl: '#013369',
    nba: '#1d428a',
    mlb: '#002d72',
    soccer: '#38003c',
    ncaaf: '#013369',
    ncaab: '#1d428a',
  }
  return colors[sport] || '#6b7280'
}

/**
 * Format relative time
 */
export function formatRelativeTime(date: string | Date): string {
  const now = new Date()
  const target = new Date(date)
  const diffMs = target.getTime() - now.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 0) {
    return 'Started'
  }
  if (diffMins < 60) {
    return `${diffMins}m`
  }
  if (diffHours < 24) {
    return `${diffHours}h`
  }
  return `${diffDays}d`
}
