export interface RoleAlert {
  type: "critical" | "warning" | "ok" | "info";
  label: string;
}
