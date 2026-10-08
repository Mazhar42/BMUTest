import { unwrap } from "@bmu/api-client";
import { formatDateTime, formatMoney, localMobile, useI18n } from "@bmu/i18n";
import { Button, Card, CardBody, CardHeader, EmptyState, OrderCode, PageHeader, Table, TD, TH, TR } from "@bmu/ui";
import { useQuery } from "@tanstack/react-query";
import { FilePlus2, IdCard } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { PatientFinder, patientLine, type StaffPatient } from "../components/PatientFinder";
import { OrderStatusBadge } from "../components/StatusBadge";
import { api } from "../lib/api";
import { useSession } from "../lib/session";

export default function PatientsPage() {
  const { t, lang } = useI18n();
  const { can } = useSession();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [patient, setPatient] = useState<StaffPatient | null>(null);
  const orders = useQuery({
    queryKey: ["patient-orders", patient?.id],
    queryFn: () =>
      unwrap(api.GET("/api/v1/staff/patients/{patient_id}/orders", { params: { path: { patient_id: patient!.id } } })),
    enabled: !!patient,
  });

  return (
    <div>
      <PageHeader eyebrow={t("nav.groups.frontDesk")} title={t("nav.items.patients")} subtitle={t("staff.patients.subtitle")} />
      <div className="grid gap-5 xl:grid-cols-[1fr_1.2fr]">
        <Card>
          <CardBody>
            <PatientFinder onPick={setPatient} initialQuery={params.get("q") ?? ""} />
          </CardBody>
        </Card>
        <Card>
          {patient ? (
            <>
              <CardHeader
                icon={<IdCard className="size-4" />}
                title={
                  <>
                    {patient.full_name}
                    {patient.full_name_bn && <span className="ml-2 font-normal text-sand-500">{patient.full_name_bn}</span>}
                  </>
                }
                subtitle={`${patientLine(patient, t)} · ${t(`enums.channel.${patient.created_channel}`)}`}
                action={
                  can("order.create_walkin") && (
                    <Button
                      size="sm"
                      icon={<FilePlus2 className="size-4" />}
                      onClick={() => navigate(`/helpdesk?patient=${patient.id}`)}
                    >
                      {t("staff.patients.newOrder")}
                    </Button>
                  )
                }
              />
              <CardBody className="grid grid-cols-2 gap-3 text-[14px]">
                <div>
                  <div className="text-[12px] text-sand-500">{t("common.mobile")}</div>
                  {patient.mobile ? localMobile(patient.mobile) : "—"}
                </div>
                <div>
                  <div className="text-[12px] text-sand-500">{t("staff.patients.hospitalNo")}</div>
                  {patient.hospital_patient_no ?? "—"}
                </div>
                <div>
                  <div className="text-[12px] text-sand-500">{t("staff.patients.account")}</div>
                  {patient.account_id ? t("staff.patients.hasAccount") : t("staff.patients.noAccount")}
                </div>
                <div>
                  <div className="text-[12px] text-sand-500">{t("staff.patients.registered")}</div>
                  {formatDateTime(patient.created_at, lang)}
                </div>
              </CardBody>
              <Table>
                <thead>
                  <tr>
                    <TH>{t("common.code")}</TH>
                    <TH>{t("staff.orders.tests")}</TH>
                    <TH>{t("common.total")}</TH>
                    <TH>{t("common.status")}</TH>
                  </tr>
                </thead>
                <tbody>
                  {(orders.data ?? []).map((o) => (
                    <TR key={o.id}>
                      <TD>
                        <Link to={`/orders/${o.order_code}`} className="hover:underline">
                          <OrderCode code={o.order_code ?? ""} size="sm" />
                        </Link>
                      </TD>
                      <TD className="text-[13px]">{o.tests.join(", ")}</TD>
                      <TD className="tabular">{formatMoney(o.total, lang)}</TD>
                      <TD>
                        <OrderStatusBadge status={o.status} />
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
              {orders.data?.length === 0 && <p className="p-6 text-center text-[13px] text-sand-500">{t("staff.patients.noOrders")}</p>}
            </>
          ) : (
            <EmptyState icon={<IdCard className="size-6" />} title={t("staff.patients.pick")} body={t("staff.patients.pickHint")} />
          )}
        </Card>
      </div>
    </div>
  );
}
