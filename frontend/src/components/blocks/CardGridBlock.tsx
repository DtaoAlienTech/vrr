import { Section, SectionHead } from "@/components/ui/Section";
import type { CardGridData } from "@/lib/content/types";

/** One block, three looks: numbered cards, icon tiles, or steps. */
export function CardGridBlock({ data }: { data: CardGridData }) {
  return (
    <Section tone={data.tone}>
      <SectionHead title={data.heading} intro={data.intro} />
      {data.variant === "numbered" && (
        <div className="why">
          {data.cards.map((card, index) => (
            <div key={card.title}>
              <b>{String(index + 1).padStart(2, "0")}</b>
              <h3>{card.title}</h3>
              {card.text && <p>{card.text}</p>}
            </div>
          ))}
        </div>
      )}
      {data.variant === "tiles" && (
        <div className="tiles">
          {data.cards.map((card) => (
            <div key={card.title} className="tile">
              <i />
              {card.title}
            </div>
          ))}
        </div>
      )}
      {data.variant === "steps" && (
        <div className="steps">
          {data.cards.map((card) => (
            <div key={card.title} className="step">
              <h3>{card.title}</h3>
              {card.text && <p>{card.text}</p>}
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}
