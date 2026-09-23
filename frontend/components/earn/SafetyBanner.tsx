type Props = {
  age: string;
  onAgeChange: (value: string) => void;
};

export function SafetyBanner({ age, onAgeChange }: Props) {
  return (
    <section className="glass-panel premium-edge p-5 border-forge-warn/25 space-y-3">
      <p className="section-label text-forge-warn">SAFETY FIRST · १४+</p>
      <p className="text-sm text-neutral-300 leading-relaxed">
        For users aged 14–17, involve a parent or guardian where required. Do not share OTPs, wallet PINs,
        citizenship numbers, or passwords. Do not bypass KYC, school, labor, contract, or payment rules.
        Paid work and payment-account eligibility depend on current Nepalese law and provider requirements.
      </p>
      <label className="block max-w-xs">
        <span className="text-xs text-neutral-500">Your real age</span>
        <input
          className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-forge-accent2/50"
          type="number"
          min={14}
          max={120}
          value={age}
          onChange={(e) => onAgeChange(e.target.value)}
          placeholder="14 or older"
        />
      </label>
    </section>
  );
}
