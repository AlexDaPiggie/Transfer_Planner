// Broad goals complement Major without repeating academic subject categories.
export const INTEREST_CATEGORIES = [
  ["transfer", "Transfer"],
  ["career and scholarships", "Career & Scholarships"],
  ["campus life", "Campus Life"],
];

const LEGACY_INTERESTS = {
  "careers and internships": "career and scholarships",
  "scholarships and financial aid": "career and scholarships",
  "research and projects": "career and scholarships",
  "business and entrepreneurship": "career and scholarships",
  "robotics": "career and scholarships", "science and research": "career and scholarships",
  "academic skills": "career and scholarships",
  "clubs and community": "campus life", "arts and culture": "campus life",
  "wellness and recreation": "campus life", "art and design": "campus life",
  "photography": "campus life", "music and performing arts": "campus life",
  "culture and languages": "campus life", "clubs and social events": "campus life",
  "volunteering": "campus life", "health and wellness": "campus life",
  "sports and outdoors": "campus life",
};

export function interestChoices(saved = []) {
  const selected = new Set(saved.map(value => {
    const text = value.trim().toLowerCase();
    const known = INTEREST_CATEGORIES.find(([key, label]) => [key, label].some(item => item.toLowerCase() === text));
    return known ? known[0] : LEGACY_INTERESTS[text];
  }));
  return INTEREST_CATEGORIES.map(([value, label]) => ({ value, label, selected: selected.has(value) }));
}
