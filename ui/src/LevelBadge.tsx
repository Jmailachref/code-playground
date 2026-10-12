import { levelLabel, type Level } from "./api";

export function LevelBadge({ level }: { level: Level }) {
  return <span className={`badge badge-level-${level}`}>{levelLabel[level]}</span>;
}
