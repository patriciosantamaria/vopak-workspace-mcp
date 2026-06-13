import { VopakSlideGenerator } from './generator.ts';

const generator = new VopakSlideGenerator('.agents/skills/slide_designer/templates/vopak_2025/layouts.json');

const testSlides = [
  {
    title: "Vopak 2025 Strategy",
    body: "1. Infrastructure Expansion\n2. Sustainability Focus\n3. Digital Transformation"
  },
  {
    title: "Global Reach",
    body: "Operational excellence across 23 countries and 70+ terminals.",
    generated_image: "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&q=80&w=960"
  },
  {
    title: "Sustainability Goals",
    body: "Net-zero ambition by 2050. Investing in hydrogen and ammonia storage solutions."
  }
];

console.log("--- GENERATING TEST REQUESTS ---");
const requests = generator.generateSlideRequests("PREVIEW_ID", testSlides);
console.log(requests);
console.log("--- DONE ---");
