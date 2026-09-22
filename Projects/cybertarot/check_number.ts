
import deckJson from './src/data/tarot-deck.json';

const cards = deckJson.cards;
let missingNumber = 0;
for (const card of cards) {
  if (card.number === undefined || card.number === null) {
    console.log('Missing number:', card.id, card.name);
    missingNumber++;
  }
}
console.log('Total cards:', cards.length);
console.log('Missing number:', missingNumber);
