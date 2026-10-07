import React, { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { X } from "lucide-react";
import { sanitizeAmount } from "@/lib/format";

let rowIdCounter = 0;

function parseValue(value) {
  if (!value) return [{ id: ++rowIdCounter, name: "", price: "" }];
  const rows = value
    .split("\n")
    .map((l) => {
      const parts = l.split(" - ");
      return { id: ++rowIdCounter, name: parts[0]?.trim() || "", price: sanitizeAmount(parts.slice(1).join(" - ").trim()) };
    })
    .filter((r) => r.name || r.price);
  return rows.length ? rows : [{ id: ++rowIdCounter, name: "", price: "" }];
}

function rowsToString(rs) {
  return rs
    .filter((r) => r.name.trim() || r.price.trim())
    .map((r) => (r.price.trim() ? `${r.name} - ${r.price}` : r.name))
    .join("\n");
}

export default function DescriptionGrid({ value, onChange }) {
  const [rows, setRows] = useState(() => parseValue(value));

  useEffect(() => {
    const currentStr = rowsToString(rows);
    if (value !== currentStr) {
      setRows(parseValue(value));
    }
  }, [value]);

  const handleChange = (id, field, val) => {
    let newRows = rows.map((r) => (r.id === id ? { ...r, [field]: val } : r));

    newRows = newRows.filter((r) => r.name.trim() || r.price.trim());
    if (newRows.length === 0) newRows = [{ id: ++rowIdCounter, name: "", price: "" }];

    const last = newRows[newRows.length - 1];
    if (last && last.name.trim() && last.price.trim()) {
      newRows.push({ id: ++rowIdCounter, name: "", price: "" });
    }

    setRows(newRows);
    onChange(rowsToString(newRows));
  };

  const removeRow = (id) => {
    let newRows = rows.filter((r) => r.id !== id);
    if (newRows.length === 0) newRows = [{ id: ++rowIdCounter, name: "", price: "" }];
    const last = newRows[newRows.length - 1];
    if (last && (last.name.trim() || last.price.trim())) {
      newRows.push({ id: ++rowIdCounter, name: "", price: "" });
    }
    setRows(newRows);
    onChange(rowsToString(newRows));
  };

  return (
    <div className="space-y-2">
      {rows.map((row, i) => (
        <div key={row.id} className="flex items-center gap-2">
          <div className="grid grid-cols-2 gap-2 flex-1">
            <Input
              value={row.name}
              onChange={(e) => handleChange(row.id, "name", e.target.value)}
              placeholder={`Artículo ${i + 1}`}
              className="h-9"
            />
            <Input
              inputMode="decimal"
              value={row.price}
              onChange={(e) => handleChange(row.id, "price", sanitizeAmount(e.target.value))}
              placeholder="Precio"
              className="h-9"
            />
          </div>
          {(row.name || row.price) && (
            <button
              onClick={() => removeRow(row.id)}
              className="text-slate-300 hover:text-red-500 transition-colors p-1 shrink-0"
              type="button"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}