import { unwrap, type Schemas } from "@bmu/api-client";
import { useI18n } from "@bmu/i18n";
import {
  Badge,
  Button,
  Card,
  Checkbox,
  Dialog,
  Dropdown,
  Field,
  Input,
  PageHeader,
  Select,
  Switch,
  Table,
  TD,
  TH,
  toast,
  TR,
} from "@bmu/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, MoreHorizontal, Pencil, Plus, ShieldOff } from "lucide-react";
import { useState } from "react";

import { api } from "../lib/api";
import { useErrorToast } from "../lib/errors";

type Staff = Schemas["StaffOut"];
type RoleName = Schemas["RoleIn"]["role"];

const ROLES: RoleName[] = [
  "HELP_DESK",
  "VERIFIER",
  "BANK_TELLER",
  "CASHIER",
  "COLLECTOR",
  "LAB_RECEPTION",
  "TECHNICIAN",
  "PATHOLOGIST",
  "REPORT_DESK",
  "WAIVER_APPROVER",
  "LAB_ADMIN",
  "AUDITOR",
  "SUPER_ADMIN",
];
const SCOPED: RoleName[] = ["TECHNICIAN", "PATHOLOGIST"];

export default function StaffAdminPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const [editing, setEditing] = useState<Staff | "new" | null>(null);
  const [resetting, setResetting] = useState<Staff | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const staff = useQuery({ queryKey: ["staff"], queryFn: () => unwrap(api.GET("/api/v1/staff/admin/staff")) });
  const depts = useQuery({ queryKey: ["departments"], queryFn: () => unwrap(api.GET("/api/v1/staff/catalog/departments")) });
  const deptName = (id: string | null) => depts.data?.find((d) => d.id === id)?.code;

  const resetTotp = useMutation({
    mutationFn: (id: string) => unwrap(api.POST("/api/v1/staff/admin/staff/{staff_id}/reset-totp", { params: { path: { staff_id: id } } })),
    onSuccess: () => toast.success(t("staff.admin.totpReset")),
    onError,
  });
  const resetPassword = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/staff/admin/staff/{staff_id}/reset-password", {
          params: { path: { staff_id: resetting!.id } },
          body: { new_password: newPassword },
        }),
      ),
    onSuccess: () => {
      toast.success(t("staff.admin.passwordReset"));
      setResetting(null);
      void qc.invalidateQueries({ queryKey: ["staff"] });
    },
    onError,
  });

  return (
    <div>
      <PageHeader
        eyebrow={t("nav.groups.admin")}
        title={t("nav.items.staff")}
        subtitle={t("staff.admin.subtitle")}
        actions={
          <Button icon={<Plus className="size-4" />} onClick={() => setEditing("new")}>
            {t("staff.admin.new")}
          </Button>
        }
      />
      <Card>
        <Table>
          <thead>
            <tr>
              <TH>{t("common.name")}</TH>
              <TH>{t("auth.username")}</TH>
              <TH>{t("staff.admin.roles")}</TH>
              <TH>{t("staff.admin.twoStep")}</TH>
              <TH>{t("common.status")}</TH>
              <TH />
            </tr>
          </thead>
          <tbody>
            {(staff.data ?? []).map((s) => (
              <TR key={s.id} className={s.is_active ? "" : "opacity-50"}>
                <TD>
                  <div className="font-semibold">{s.full_name}</div>
                  <div className="text-[12px] text-sand-500">{s.designation ?? ""}</div>
                </TD>
                <TD className="font-mono text-[13px]">{s.username}</TD>
                <TD>
                  <div className="flex flex-wrap gap-1">
                    {s.roles.map((r) => (
                      <Badge key={`${r.role}${r.department_id ?? ""}`} tone="brand">
                        {t(`roles.${r.role}`)}
                        {r.department_id && ` · ${deptName(r.department_id) ?? ""}`}
                      </Badge>
                    ))}
                  </div>
                </TD>
                <TD>{s.totp_enabled ? <Badge tone="ok">{t("common.yes")}</Badge> : <Badge>{t("common.no")}</Badge>}</TD>
                <TD>
                  {!s.is_active ? (
                    <Badge>{t("staff.admin.inactive")}</Badge>
                  ) : s.locked_until && new Date(s.locked_until) > new Date() ? (
                    <Badge tone="danger">{t("staff.admin.locked")}</Badge>
                  ) : (
                    <Badge tone="ok">{t("staff.admin.active")}</Badge>
                  )}
                </TD>
                <TD className="text-right">
                  <Dropdown
                    trigger={
                      <Button size="sm" variant="ghost" aria-label={t("common.actions")}>
                        <MoreHorizontal className="size-4" />
                      </Button>
                    }
                    items={[
                      { label: t("common.edit"), icon: <Pencil className="size-4" />, onSelect: () => setEditing(s) },
                      {
                        label: t("staff.admin.resetPassword"),
                        icon: <KeyRound className="size-4" />,
                        onSelect: () => {
                          setNewPassword("");
                          setResetting(s);
                        },
                      },
                      { label: t("staff.admin.resetTotp"), icon: <ShieldOff className="size-4" />, onSelect: () => resetTotp.mutate(s.id) },
                    ]}
                  />
                </TD>
              </TR>
            ))}
          </tbody>
        </Table>
      </Card>
      {editing && <StaffDialog staff={editing === "new" ? null : editing} depts={depts.data ?? []} onClose={() => setEditing(null)} />}
      <Dialog
        open={!!resetting}
        onOpenChange={(v) => !v && setResetting(null)}
        title={t("staff.admin.resetPassword")}
        description={resetting?.full_name}
        footer={
          <Button loading={resetPassword.isPending} disabled={newPassword.length < 10} onClick={() => resetPassword.mutate()}>
            {t("common.save")}
          </Button>
        }
      >
        <Field label={t("staff.admin.newPassword")} hint={t("staff.admin.passwordHint")}>
          <Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} autoFocus />
        </Field>
      </Dialog>
    </div>
  );
}

function StaffDialog({
  staff,
  depts,
  onClose,
}: {
  staff: Staff | null;
  depts: Schemas["DepartmentOut"][];
  onClose: () => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const onError = useErrorToast();
  const [f, setF] = useState({
    username: staff?.username ?? "",
    full_name: staff?.full_name ?? "",
    full_name_bn: staff?.full_name_bn ?? "",
    designation: staff?.designation ?? "",
    mobile: staff?.mobile ?? "",
    password: "",
    is_active: staff?.is_active ?? true,
  });
  const [roles, setRoles] = useState<Schemas["RoleIn"][]>(
    staff?.roles.map((r) => ({ role: r.role, department_id: r.department_id })) ?? [],
  );

  const toggle = (role: RoleName, on: boolean) =>
    setRoles((rs) => (on ? [...rs, { role, department_id: null }] : rs.filter((r) => r.role !== role)));

  const save = useMutation({
    mutationFn: () =>
      staff
        ? unwrap(
            api.PATCH("/api/v1/staff/admin/staff/{staff_id}", {
              params: { path: { staff_id: staff.id } },
              body: {
                full_name: f.full_name,
                full_name_bn: f.full_name_bn || null,
                designation: f.designation || null,
                mobile: f.mobile || null,
                is_active: f.is_active,
                roles,
              },
            }),
          )
        : unwrap(
            api.POST("/api/v1/staff/admin/staff", {
              body: {
                username: f.username.trim().toLowerCase(),
                full_name: f.full_name,
                full_name_bn: f.full_name_bn || null,
                designation: f.designation || null,
                mobile: f.mobile || null,
                password: f.password,
                roles,
              },
            }),
          ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["staff"] });
      onClose();
    },
    onError,
  });

  return (
    <Dialog
      open
      onOpenChange={(v) => !v && onClose()}
      size="lg"
      title={staff ? staff.full_name : t("staff.admin.new")}
      footer={
        <Button
          loading={save.isPending}
          onClick={() => save.mutate()}
          disabled={!f.full_name || roles.length === 0 || (!staff && (f.password.length < 10 || !f.username))}
        >
          {t("common.save")}
        </Button>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {!staff && (
          <Field label={t("auth.username")} hint={t("staff.admin.usernameHint")}>
            <Input value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} />
          </Field>
        )}
        {!staff && (
          <Field label={t("auth.password")} hint={t("staff.admin.passwordHint")}>
            <Input type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
          </Field>
        )}
        <Field label={t("staff.patients.fullName")}>
          <Input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} />
        </Field>
        <Field label={t("staff.patients.fullNameBn")}>
          <Input value={f.full_name_bn} onChange={(e) => setF({ ...f, full_name_bn: e.target.value })} lang="bn" />
        </Field>
        <Field label={t("staff.admin.designation")}>
          <Input value={f.designation} onChange={(e) => setF({ ...f, designation: e.target.value })} />
        </Field>
        <Field label={t("common.mobile")}>
          <Input value={f.mobile} onChange={(e) => setF({ ...f, mobile: e.target.value })} />
        </Field>
      </div>
      <h4 className="mb-2 mt-6 text-[13px] font-semibold uppercase tracking-wider text-sand-500">{t("staff.admin.roles")}</h4>
      <div className="grid gap-2 sm:grid-cols-2">
        {ROLES.map((role) => {
          const current = roles.find((r) => r.role === role);
          return (
            <div key={role} className="flex items-center gap-2 rounded-lg border border-sand-200 px-3 py-2">
              <Checkbox label={t(`roles.${role}`)} checked={!!current} onChange={(e) => toggle(role, e.target.checked)} />
              {current && SCOPED.includes(role) && (
                <Select
                  className="ml-auto h-8 w-32 text-[13px]"
                  value={current.department_id ?? ""}
                  onChange={(e) =>
                    setRoles((rs) => rs.map((r) => (r.role === role ? { ...r, department_id: e.target.value || null } : r)))
                  }
                >
                  <option value="">{t("common.all")}</option>
                  {depts.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.code}
                    </option>
                  ))}
                </Select>
              )}
            </div>
          );
        })}
      </div>
      {staff && (
        <div className="mt-5">
          <Switch checked={f.is_active} onCheckedChange={(v) => setF({ ...f, is_active: v })} label={t("staff.admin.active")} />
        </div>
      )}
    </Dialog>
  );
}
