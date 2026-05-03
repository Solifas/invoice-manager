"use client";

import { useEffect, useId, useState } from "react";

import { CurrencyOption } from "@/lib/types";

function getCurrencyLabel(option: CurrencyOption) {
  return `${option.code} · ${option.name}`;
}

function resolveCurrencyOption(query: string, options: CurrencyOption[]) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return null;
  }

  return (
    options.find((option) => option.code.toLowerCase() === normalizedQuery) ||
    options.find((option) => getCurrencyLabel(option).toLowerCase() === normalizedQuery) ||
    null
  );
}

export function SearchableCurrencySelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: CurrencyOption[];
  onChange: (code: string) => void;
}) {
  const listId = useId();
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const selected = options.find((option) => option.code === value);
    setQuery(selected ? getCurrencyLabel(selected) : value);
  }, [options, value]);

  const normalizedQuery = query.trim().toLowerCase();
  const filteredOptions = normalizedQuery
    ? options.filter((option) => {
        const optionLabel = getCurrencyLabel(option).toLowerCase();
        return optionLabel.includes(normalizedQuery) || option.code.toLowerCase().includes(normalizedQuery);
      })
    : options;

  const visibleOptions = filteredOptions.slice(0, 12);

  return (
    <label className="searchable-select">
      <span className="field-label">{label}</span>
      <div className="searchable-select-shell">
        <input
          aria-autocomplete="list"
          aria-controls={listId}
          aria-expanded={isOpen}
          className="input"
          onBlur={() => {
            window.setTimeout(() => {
              const matchedOption = resolveCurrencyOption(query, options);
              if (matchedOption) {
                onChange(matchedOption.code);
                setQuery(getCurrencyLabel(matchedOption));
                setIsOpen(false);
                return;
              }

              setIsOpen(false);
              const selected = options.find((option) => option.code === value);
              setQuery(selected ? getCurrencyLabel(selected) : value);
            }, 120);
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              const matchedOption = resolveCurrencyOption(query, options) || visibleOptions[0];
              if (!matchedOption) {
                return;
              }
              event.preventDefault();
              onChange(matchedOption.code);
              setQuery(getCurrencyLabel(matchedOption));
              setIsOpen(false);
            }

            if (event.key === "Escape") {
              setIsOpen(false);
            }
          }}
          placeholder="Search currency by code or name"
          role="combobox"
          value={query}
        />
        {isOpen ? (
          <div className="searchable-select-menu" id={listId} role="listbox">
            {visibleOptions.length ? (
              visibleOptions.map((option) => (
                <button
                  className={`searchable-select-option${option.code === value ? " is-active" : ""}`}
                  key={option.code}
                  onMouseDown={(event) => {
                    event.preventDefault();
                    onChange(option.code);
                    setQuery(getCurrencyLabel(option));
                    setIsOpen(false);
                  }}
                  role="option"
                  type="button"
                >
                  {getCurrencyLabel(option)}
                </button>
              ))
            ) : (
              <div className="searchable-select-empty">No currencies matched your search.</div>
            )}
          </div>
        ) : null}
      </div>
    </label>
  );
}
