import { Hammer } from "lucide-react";

interface StubPageProps {
  title: string;
  description: string;
  milestone: string;
}

/**
 * Placeholder per le pagine non ancora implementate. Mostra il
 * milestone in cui arriverà il contenuto, così l'utente che apre la
 * voce del menu non si ritrova davanti a una pagina vuota e in più
 * sa quando aspettarsi il pezzo mancante.
 */
export function StubPage({ title, description, milestone }: StubPageProps) {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-sm text-zinc-500">{description}</p>
      </header>
      <section className="flex items-start gap-3 rounded-xl border border-dashed border-amber-500/30 bg-amber-500/10 p-5">
        <Hammer className="mt-0.5 text-amber-300" size={20} />
        <div>
          <h2 className="text-sm font-semibold text-amber-100">
            In arrivo in {milestone}
          </h2>
          <p className="mt-1 text-sm text-amber-200">
            Questa schermata è uno stub: la UI è scaffold-ata ma la
            logica viene cablata insieme al milestone indicato. Il
            backend espone già gli endpoint che servono, quindi è
            pronto a quel passaggio.
          </p>
        </div>
      </section>
    </div>
  );
}
