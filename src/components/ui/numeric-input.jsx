import * as React from "react";
import { Input } from "@/components/ui/input";
import { sanitizeAmount } from "@/lib/format";

const NumericInput = React.forwardRef(({ value, onChange, ...props }, ref) => (
  <Input
    ref={ref}
    inputMode="decimal"
    value={sanitizeAmount(value)}
    onChange={(e) => onChange?.(sanitizeAmount(e.target.value))}
    {...props}
  />
));
NumericInput.displayName = "NumericInput";

export { NumericInput };