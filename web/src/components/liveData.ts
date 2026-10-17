import type { LiveSample, PatternKey } from "../api";

// Sample columns: [seq, level, t, trial, phase, lx, ly, rx, ry, tlx, tly, trx, try, reached_l, reached_r]
export const LX = 5,
  LY = 6,
  RX = 7,
  RY = 8,
  TLX = 9,
  TLY = 10,
  TRX = 11,
  TRY = 12;
export const HZ = 100;

export type Hand = "left" | "right";
export const HANDS: Hand[] = ["left", "right"];

export function handPos(s: LiveSample, hand: Hand): [number, number] {
  return hand === "left" ? [s[LX], s[LY]] : [s[RX], s[RY]];
}

export function handTarget(s: LiveSample, hand: Hand): [number, number] | null {
  const x = hand === "left" ? s[TLX] : s[TRX];
  const y = hand === "left" ? s[TLY] : s[TRY];
  return x == null || y == null ? null : [x, y];
}

export const pct = (v: number | null | undefined, digits = 0) =>
  v == null ? "—" : `${(v * 100).toFixed(digits)}%`;
export const secs = (v: number | null | undefined) =>
  v == null ? "—" : `${v.toFixed(2)} s`;

export const PATTERN_LABELS: Record<PatternKey, string> = {
  parkinson: "Slowed, smaller movements (both hands)",
  stroke: "One-sided difference between hands",
  essential_tremor: "Shake during movement",
};
export const PATTERN_ORDER: PatternKey[] = [
  "parkinson",
  "stroke",
  "essential_tremor",
];
const LEVEL_NAMES: Record<string, string> = {
  apples: "Apples",
  butterfly_left: "Butterfly (left)",
  butterfly_right: "Butterfly (right)",
  water: "Watering",
};
export const levelName = (lv: string | null | undefined) =>
  lv ? (LEVEL_NAMES[lv] ?? lv) : "";
