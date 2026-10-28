import type { ApiScenario } from "@/lib/api"
import { PACKS, baselineLever, newScenario, packLabel, skuFor } from "@/lib/catalog"
import { initialScenarios } from "./helpers"

export interface TemplateInput { pack: string; costPct: number }

/**
 * A starting point for a new case, phrased as the business question it answers. Every question template includes
 * an option that loses profit and one outside the data (refused, no numbers), so both are visible from day one.
 * The settings below are scenario inputs a user could type; every outcome is calculated by the engine.
 */
export interface CaseTemplate {
  id: string
  title: string
  blurb: string
  needs: Array<"pack" | "cost">
  name: (input: TemplateInput) => string
  question: (input: TemplateInput) => string
  build: (input: TemplateInput) => ApiScenario[]
}

const CAN = skuFor("can_330ml"), BOTTLE = skuFor("bottle_1500ml"), MULTIPACK = skuFor("multipack_6x330ml")
const price = (index: number) => ({ ...baselineLever, price_index: index })
const promo = (depth: number, weeks = 2) => ({ ...baselineLever, promo_depth_pct: depth, mechanic: "TPR", promo_weeks_per_month: weeks })
const short = (pack: string) => PACKS.find((p) => p.id === pack)?.short ?? pack

export const DEFAULT_INPUT: TemplateInput = { pack: "bottle_1500ml", costPct: 8 }

export const TEMPLATES: CaseTemplate[] = [
  {
    id: "costs",
    title: "Costs are rising",
    blurb: "Input costs are up. Which response protects gross profit?",
    needs: ["cost"],
    name: ({ costPct }) => `Input costs +${costPct}%: how do we respond?`,
    question: ({ costPct }) => `Aluminium, PET and sugar costs are up ${costPct}%. Which price, pack or promotion response protects gross profit without losing more than 5% volume?`,
    build: ({ costPct }) => {
      const shock = { aluminium_pct: costPct, pet_resin_pct: costPct, sugar_pct: costPct }
      const withCosts = (s: ApiScenario): ApiScenario => ({ ...s, cost_shock: shock })
      return [
        withCosts(newScenario(`Absorb the cost (inputs +${costPct}%)`)),
        withCosts(newScenario("Take 3% on the large packs", { [BOTTLE]: price(1.03), [MULTIPACK]: price(1.03) })),
        withCosts(newScenario("Take 4% on the can", { [CAN]: price(1.04) })),
        withCosts(newScenario("Raise the can, make the 6-pack cheaper", { [CAN]: price(1.04), [MULTIPACK]: price(0.98) })),
        withCosts(newScenario("Run a 20% can promotion", { [CAN]: promo(20) })),
        withCosts(newScenario("Recover it all on the can (+50%)", { [CAN]: price(1.5) })),
      ]
    },
  },
  {
    id: "price",
    title: "Should we take price?",
    blurb: "Test small price rises on one pack, and a cut for contrast.",
    needs: ["pack"],
    name: ({ pack }) => `Price rise on the ${short(pack)}`,
    question: ({ pack }) => `Should we raise the price of the ${packLabel(pack)}, and by how much, without losing more than 5% volume?`,
    build: ({ pack }) => {
      const sku = skuFor(pack)
      return [
        newScenario("Baseline"),
        newScenario(`${short(pack)} +2%`, { [sku]: price(1.02) }),
        newScenario(`${short(pack)} +3%`, { [sku]: price(1.03) }),
        newScenario(`${short(pack)} +5%`, { [sku]: price(1.05) }),
        newScenario(`${short(pack)} cut 4%`, { [sku]: price(0.96) }),
        newScenario(`${short(pack)} +50%`, { [sku]: price(1.5) }),
      ]
    },
  },
  {
    id: "promo",
    title: "Is this promotion worth it?",
    blurb: "Compare promotion depths on one pack.",
    needs: ["pack"],
    name: ({ pack }) => `Promotion depth on the ${short(pack)}`,
    question: ({ pack }) => `Does a promotion on the ${packLabel(pack)} pay for itself in gross profit, and how deep should it be?`,
    build: ({ pack }) => {
      const sku = skuFor(pack)
      return [
        newScenario("Baseline"),
        newScenario(`${short(pack)} 10% off`, { [sku]: promo(10) }),
        newScenario(`${short(pack)} 20% off`, { [sku]: promo(20) }),
        newScenario(`${short(pack)} 30% off`, { [sku]: promo(30) }),
        newScenario(`${short(pack)} 40% off`, { [sku]: promo(40) }),
      ]
    },
  },
  {
    id: "mix",
    title: "Move shoppers to bigger packs",
    blurb: "Price small packs up and large packs slightly down.",
    needs: [],
    name: () => "Steer shoppers to bigger packs",
    question: () => "Can we grow gross profit by nudging shoppers from the can and 500 ml to the 1.5 L and the 6-pack?",
    build: () => {
      const PET = skuFor("pet_500ml")
      return [
        newScenario("Baseline"),
        newScenario("Small packs +3%, large packs −2%", { [CAN]: price(1.03), [PET]: price(1.03), [BOTTLE]: price(0.98), [MULTIPACK]: price(0.98) }),
        newScenario("Can +4%, 6-pack −2%", { [CAN]: price(1.04), [MULTIPACK]: price(0.98) }),
        newScenario("Large packs −4%, no change on small", { [BOTTLE]: price(0.96), [MULTIPACK]: price(0.96) }),
        newScenario("6-pack 20% off", { [MULTIPACK]: promo(20) }),
        newScenario("Can +50%", { [CAN]: price(1.5) }),
      ]
    },
  },
  {
    id: "example",
    title: "Example case",
    blurb: "A price move, a promotion, a combination, a loser and a refusal.",
    needs: [],
    name: () => "",
    question: () => "",
    build: () => initialScenarios,
  },
  {
    id: "blank",
    title: "Blank",
    blurb: "Baseline only. Build your own options.",
    needs: [],
    name: () => "",
    question: () => "",
    build: () => [newScenario("Baseline")],
  },
]
