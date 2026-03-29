import { useState, useMemo } from 'react';

interface Props {
  defaultPrice?: number;
  defaultRent?: number;
}

export default function RentalYieldCalculator({ defaultPrice = 300000, defaultRent = 1200 }: Props) {
  const [price, setPrice] = useState(defaultPrice);
  const [rent, setRent] = useState(defaultRent);
  const [annualCosts, setAnnualCosts] = useState(2000);

  const result = useMemo(() => {
    if (price <= 0 || rent <= 0) return null;
    const annualRent = rent * 12;
    const grossYield = (annualRent / price) * 100;
    const netIncome = annualRent - annualCosts;
    const netYield = (netIncome / price) * 100;
    const yearsToBreakeven = price / netIncome;

    return { annualRent, grossYield, netIncome, netYield, yearsToBreakeven };
  }, [price, rent, annualCosts]);

  const fmt = (n: number) => n.toLocaleString('en-GB', { maximumFractionDigits: 0 });

  return (
    <div className="bg-surface rounded-xl p-4 space-y-4">
      <h4 className="text-sm font-semibold text-ink">Rental Yield Calculator</h4>

      <div className="grid grid-cols-2 gap-3">
        <label className="space-y-1">
          <span className="text-xs text-ink-muted">Purchase Price</span>
          <input
            type="number"
            value={price}
            onChange={(e) => setPrice(Number(e.target.value))}
            className="w-full h-9 px-3 rounded-lg border border-divider bg-white text-sm text-ink focus:outline-none focus:border-brand-500"
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs text-ink-muted">Monthly Rent</span>
          <input
            type="number"
            value={rent}
            onChange={(e) => setRent(Number(e.target.value))}
            className="w-full h-9 px-3 rounded-lg border border-divider bg-white text-sm text-ink focus:outline-none focus:border-brand-500"
          />
        </label>
        <label className="space-y-1 col-span-2">
          <span className="text-xs text-ink-muted">Annual Costs (maintenance, insurance, mgmt fees)</span>
          <input
            type="number"
            value={annualCosts}
            onChange={(e) => setAnnualCosts(Number(e.target.value))}
            className="w-full h-9 px-3 rounded-lg border border-divider bg-white text-sm text-ink focus:outline-none focus:border-brand-500"
          />
        </label>
      </div>

      {result && (
        <div className="grid grid-cols-2 gap-3 pt-2">
          <div className="bg-white rounded-lg p-3 border border-divider">
            <div className="text-xs text-ink-muted">Gross Yield</div>
            <div className={`text-lg font-bold ${result.grossYield >= 5 ? 'text-signal-green' : result.grossYield >= 3 ? 'text-signal-amber' : 'text-signal-red'}`}>
              {result.grossYield.toFixed(2)}%
            </div>
          </div>
          <div className="bg-white rounded-lg p-3 border border-divider">
            <div className="text-xs text-ink-muted">Net Yield</div>
            <div className={`text-lg font-bold ${result.netYield >= 4 ? 'text-signal-green' : result.netYield >= 2 ? 'text-signal-amber' : 'text-signal-red'}`}>
              {result.netYield.toFixed(2)}%
            </div>
          </div>
          <div className="bg-white rounded-lg p-3 border border-divider">
            <div className="text-xs text-ink-muted">Annual Rent</div>
            <div className="text-lg font-bold text-ink">{'\u00A3'}{fmt(result.annualRent)}</div>
          </div>
          <div className="bg-white rounded-lg p-3 border border-divider">
            <div className="text-xs text-ink-muted">Net Income/yr</div>
            <div className="text-lg font-bold text-ink">{'\u00A3'}{fmt(result.netIncome)}</div>
          </div>
        </div>
      )}
    </div>
  );
}
