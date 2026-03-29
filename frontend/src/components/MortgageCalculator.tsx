import { useState, useMemo } from 'react';

interface Props {
  defaultPrice?: number;
  medianEarnings?: number;
}

export default function MortgageCalculator({ defaultPrice = 300000, medianEarnings }: Props) {
  const [price, setPrice] = useState(defaultPrice);
  const [deposit, setDeposit] = useState(Math.round(defaultPrice * 0.1));
  const [rate, setRate] = useState(4.5);
  const [term, setTerm] = useState(25);

  const result = useMemo(() => {
    const loan = price - deposit;
    if (loan <= 0 || rate <= 0 || term <= 0) return null;
    const monthlyRate = rate / 100 / 12;
    const n = term * 12;
    const monthly = (loan * monthlyRate * Math.pow(1 + monthlyRate, n)) / (Math.pow(1 + monthlyRate, n) - 1);
    const totalCost = monthly * n;
    const totalInterest = totalCost - loan;
    const depositPct = (deposit / price) * 100;
    const ltv = ((price - deposit) / price) * 100;
    const annualRepayment = monthly * 12;
    const affordabilityPct = medianEarnings ? (annualRepayment / medianEarnings) * 100 : null;

    return { monthly, totalCost, totalInterest, depositPct, ltv, annualRepayment, affordabilityPct };
  }, [price, deposit, rate, term, medianEarnings]);

  const fmt = (n: number) => n.toLocaleString('en-GB', { maximumFractionDigits: 0 });

  return (
    <div className="bg-surface rounded-xl p-4 space-y-4">
      <h4 className="text-sm font-semibold text-ink">Mortgage Calculator</h4>

      <div className="grid grid-cols-2 gap-3">
        <label className="space-y-1">
          <span className="text-xs text-ink-muted">Property Price</span>
          <input
            type="number"
            value={price}
            onChange={(e) => setPrice(Number(e.target.value))}
            className="w-full h-9 px-3 rounded-lg border border-divider bg-white text-sm text-ink focus:outline-none focus:border-brand-500"
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs text-ink-muted">Deposit</span>
          <input
            type="number"
            value={deposit}
            onChange={(e) => setDeposit(Number(e.target.value))}
            className="w-full h-9 px-3 rounded-lg border border-divider bg-white text-sm text-ink focus:outline-none focus:border-brand-500"
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs text-ink-muted">Interest Rate (%)</span>
          <input
            type="number"
            value={rate}
            step={0.1}
            onChange={(e) => setRate(Number(e.target.value))}
            className="w-full h-9 px-3 rounded-lg border border-divider bg-white text-sm text-ink focus:outline-none focus:border-brand-500"
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs text-ink-muted">Term (years)</span>
          <input
            type="number"
            value={term}
            onChange={(e) => setTerm(Number(e.target.value))}
            className="w-full h-9 px-3 rounded-lg border border-divider bg-white text-sm text-ink focus:outline-none focus:border-brand-500"
          />
        </label>
      </div>

      {result && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2">
          <div className="bg-white rounded-lg p-3 border border-divider">
            <div className="text-xs text-ink-muted">Monthly Payment</div>
            <div className="text-lg font-bold text-brand-600">{'\u00A3'}{fmt(result.monthly)}</div>
          </div>
          <div className="bg-white rounded-lg p-3 border border-divider">
            <div className="text-xs text-ink-muted">LTV</div>
            <div className="text-lg font-bold text-ink">{result.ltv.toFixed(0)}%</div>
          </div>
          <div className="bg-white rounded-lg p-3 border border-divider">
            <div className="text-xs text-ink-muted">Total Interest</div>
            <div className="text-lg font-bold text-ink">{'\u00A3'}{fmt(result.totalInterest)}</div>
          </div>
          {result.affordabilityPct !== null && (
            <div className="bg-white rounded-lg p-3 border border-divider col-span-2 sm:col-span-3">
              <div className="text-xs text-ink-muted">Repayment as % of Local Median Income</div>
              <div className={`text-lg font-bold ${result.affordabilityPct > 40 ? 'text-signal-red' : result.affordabilityPct > 30 ? 'text-signal-amber' : 'text-signal-green'}`}>
                {result.affordabilityPct.toFixed(1)}%
                <span className="text-xs font-normal text-ink-muted ml-2">
                  ({'\u00A3'}{fmt(result.annualRepayment)}/yr vs {'\u00A3'}{fmt(medianEarnings!)} median)
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
