import type { Language } from "./api";

interface Props {
  languages: Language[];
  value: string;
  onChange: (id: string) => void;
}

export function LanguagePicker({ languages, value, onChange }: Props) {
  return (
    <select className="select" value={value} onChange={(e) => onChange(e.target.value)} aria-label="Language">
      {languages.map((lang) => (
        <option key={lang.id} value={lang.id}>
          {lang.display_name}
        </option>
      ))}
    </select>
  );
}
