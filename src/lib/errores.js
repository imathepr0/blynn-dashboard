import { describirError } from "@/api";
import { toast } from "@/components/ui/use-toast";

/** Muestra un error de la API como aviso, con un mensaje claro en español. */
export function mostrarError(error, titulo = "No se pudo completar la acción") {
  toast({ title: titulo, description: describirError(error), variant: "destructive" });
}
