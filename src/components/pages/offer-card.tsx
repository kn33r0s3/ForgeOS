import type { BusinessOffer } from "@/lib/content";
import { Link } from "@tanstack/react-router";

export function OfferCard({ offer }: { offer: BusinessOffer }) {
  return (
    <article className="flex flex-col rounded-xl border border-line bg-surface p-6 transition-[border-color,transform] duration-150 hover:border-cyan/35">
      <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-cyan">
        Current offer
      </p>
      <h3 className="mt-5 font-display text-2xl font-semibold tracking-tight text-fg">
        {offer.title}
      </h3>
      <dl className="mt-6 grid gap-4 text-sm">
        <div>
          <dt className="font-semibold text-fg">Problem</dt>
          <dd className="mt-1 leading-relaxed text-muted">{offer.problem}</dd>
        </div>
        <div>
          <dt className="font-semibold text-fg">What Hami does</dt>
          <dd className="mt-1 leading-relaxed text-muted">{offer.does}</dd>
        </div>
        <div>
          <dt className="font-semibold text-fg">Expected value</dt>
          <dd className="mt-1 leading-relaxed text-muted">{offer.value}</dd>
        </div>
        <div>
          <dt className="font-semibold text-fg">How to start</dt>
          <dd className="mt-1 leading-relaxed text-muted">{offer.start}</dd>
        </div>
      </dl>
      <div className="mt-6 border-t border-line pt-4">
        <Link to={offer.relatedTo} className="link-arrow inline-flex min-h-10 items-center gap-2 text-sm font-bold text-cyan">
          {offer.relatedLabel}
        </Link>
      </div>
    </article>
  );
}
