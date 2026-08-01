const CASE_RANGES = {
  AUTH: 9,
  ONB: 14,
  RUN: 12,
  DISC: 10,
  RANK: 10,
  MATCH: 18,
  TRACK: 10,
  SET: 8,
  TAILOR: 8,
  DESK: 16,
  NATIVE: 10,
  REL: 12,
  A11Y: 8,
  SEC: 10,
};

export const CASE_IDS = Object.entries(CASE_RANGES).flatMap(([prefix, count]) =>
  Array.from({ length: count }, (_, index) => `${prefix}-${String(index + 1).padStart(2, "0")}`),
);
