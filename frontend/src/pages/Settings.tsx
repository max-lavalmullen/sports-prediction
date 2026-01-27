import { useSettingsStore } from '@/stores/settingsStore'

export default function Settings() {
  const settings = useSettingsStore()

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Configure your preferences and API keys
        </p>
      </div>

      {/* Display Settings */}
      <div className="bg-card rounded-lg border border-border p-6">
        <h2 className="font-semibold mb-4">Display</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Odds Format</label>
            <select
              value={settings.oddsFormat}
              onChange={(e) =>
                settings.setOddsFormat(e.target.value as 'american' | 'decimal')
              }
              className="w-full px-3 py-2 rounded-md border border-border bg-background"
            >
              <option value="american">American (-110, +150)</option>
              <option value="decimal">Decimal (1.91, 2.50)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Theme</label>
            <select
              value={settings.theme}
              onChange={(e) =>
                settings.setTheme(e.target.value as 'light' | 'dark' | 'system')
              }
              className="w-full px-3 py-2 rounded-md border border-border bg-background"
            >
              <option value="dark">Dark</option>
              <option value="light">Light</option>
              <option value="system">System</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Default Sport</label>
            <select
              value={settings.defaultSport}
              onChange={(e) => settings.setDefaultSport(e.target.value as any)}
              className="w-full px-3 py-2 rounded-md border border-border bg-background"
            >
              <option value="all">All Sports</option>
              <option value="nfl">NFL</option>
              <option value="nba">NBA</option>
              <option value="mlb">MLB</option>
              <option value="soccer">Soccer</option>
            </select>
          </div>
        </div>
      </div>

      {/* Bankroll Settings */}
      <div className="bg-card rounded-lg border border-border p-6">
        <h2 className="font-semibold mb-4">Bankroll & Staking</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              Current Bankroll ($)
            </label>
            <input
              type="number"
              value={settings.bankroll}
              onChange={(e) => settings.setBankroll(parseFloat(e.target.value))}
              className="w-full px-3 py-2 rounded-md border border-border bg-background"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Default Kelly Fraction
            </label>
            <select
              value={settings.defaultKellyFraction}
              onChange={(e) =>
                settings.setDefaultKellyFraction(parseFloat(e.target.value))
              }
              className="w-full px-3 py-2 rounded-md border border-border bg-background"
            >
              <option value="0.1">10% (Very Conservative)</option>
              <option value="0.25">25% (Quarter Kelly)</option>
              <option value="0.5">50% (Half Kelly)</option>
              <option value="1">100% (Full Kelly)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Max Stake % of Bankroll
            </label>
            <input
              type="number"
              step="0.01"
              value={settings.maxStakePercent}
              onChange={(e) =>
                settings.setMaxStakePercent(parseFloat(e.target.value))
              }
              className="w-full px-3 py-2 rounded-md border border-border bg-background"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Maximum stake regardless of Kelly suggestion (e.g., 0.05 = 5%)
            </p>
          </div>
        </div>
      </div>

      {/* Alert Settings */}
      <div className="bg-card rounded-lg border border-border p-6">
        <h2 className="font-semibold mb-4">Alerts</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Enable Value Alerts</p>
              <p className="text-sm text-muted-foreground">
                Get notified when value bets are detected
              </p>
            </div>
            <button
              onClick={() => settings.setAlertsEnabled(!settings.alertsEnabled)}
              className={`w-12 h-6 rounded-full transition-colors ${
                settings.alertsEnabled ? 'bg-primary' : 'bg-muted'
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full bg-white transition-transform ${
                  settings.alertsEnabled ? 'translate-x-6' : 'translate-x-0.5'
                }`}
              />
            </button>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Minimum Edge for Alerts
            </label>
            <input
              type="number"
              step="0.01"
              value={settings.alertMinEdge}
              onChange={(e) =>
                settings.setAlertMinEdge(parseFloat(e.target.value))
              }
              className="w-full px-3 py-2 rounded-md border border-border bg-background"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Only alert on bets with edge above this threshold (e.g., 0.03 = 3%)
            </p>
          </div>
        </div>
      </div>

      {/* API Keys */}
      <div className="bg-card rounded-lg border border-border p-6">
        <h2 className="font-semibold mb-4">API Keys</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              The Odds API Key
            </label>
            <input
              type="password"
              value={settings.oddsApiKey}
              onChange={(e) => settings.setOddsApiKey(e.target.value)}
              placeholder="Enter your API key"
              className="w-full px-3 py-2 rounded-md border border-border bg-background"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Get your free API key at{' '}
              <a
                href="https://the-odds-api.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                the-odds-api.com
              </a>
            </p>
          </div>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="bg-card rounded-lg border border-red-500/20 p-6">
        <h2 className="font-semibold mb-4 text-red-500">Danger Zone</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Reset All Settings</p>
              <p className="text-sm text-muted-foreground">
                This will reset all settings to their defaults
              </p>
            </div>
            <button className="px-4 py-2 rounded-md border border-red-500 text-red-500 hover:bg-red-500/10">
              Reset
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Clear All Data</p>
              <p className="text-sm text-muted-foreground">
                Delete all bets, predictions, and cached data
              </p>
            </div>
            <button className="px-4 py-2 rounded-md border border-red-500 text-red-500 hover:bg-red-500/10">
              Clear Data
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
