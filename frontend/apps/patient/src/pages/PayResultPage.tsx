import { unwrap } from "@bmu/api-client";
import { formatMoney, useI18n } from "@bmu/i18n";
import { Button, OrderCode, Spinner } from "@bmu/ui";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { Screen } from "../components/Layout";
import { api } from "../lib/api";

/** Where the gateway sends the patient back. The browser redirect proves nothing, so this page asks our
 *  server (which re-checks with the gateway while the payment is PENDING) until the outcome is known. */
export default function PayResultPage() {
  const { t, lang } = useI18n();
  const [params] = useSearchParams();
  const tran = params.get("tran") ?? "";
  const status = useQuery({
    queryKey: ["pay-status", tran],
    queryFn: () => unwrap(api.GET("/api/v1/patient/payments/{tran_id}", { params: { path: { tran_id: tran } } })),
    enabled: !!tran,
    refetchInterval: (q) => (q.state.data?.status === "PENDING" || q.state.data?.status === "INITIATED" ? 2500 : false),
    retry: false,
  });
  const d = status.data;
  const kind = !d ? "pending" : d.status === "SUCCESS" ? "success" : d.status === "PENDING" || d.status === "INITIATED" ? "pending" : "failed";
  const orderLink = d ? `/orders/${d.order_id}` : "/orders";

  return (
    <Screen title={t("patient.pay.resultTitle")}>
      <div className="flex flex-col items-center pt-10 text-center" data-testid="pay-result" data-kind={kind}>
        {kind === "success" && <CheckCircle2 className="size-20 text-ok-600" />}
        {kind === "failed" && <XCircle className="size-20 text-danger-600" />}
        {kind === "pending" && (status.isError ? <XCircle className="size-20 text-danger-600" /> : <Clock className="size-20 text-warn-600" />)}
        <h2 className="mt-5 text-[26px] font-bold">
          {status.isError ? t("patient.pay.notFound") : t(`patient.pay.result.${kind}.title`)}
        </h2>
        <p className="mt-2 max-w-xs text-[15px] text-sand-600">
          {status.isError ? "" : kind === "failed" ? t(`patient.pay.result.failed.${d?.status === "CANCELLED" ? "cancelled" : "body"}`) : t(`patient.pay.result.${kind}.body`)}
        </p>
        {kind === "pending" && !status.isError && <Spinner className="mt-5" />}
        {d && (
          <div className="mt-6 rounded-2xl bg-white p-4 shadow-card ring-1 ring-sand-200">
            <OrderCode code={d.order_code ?? ""} size="lg" />
            <div className="mt-1 text-[20px] font-bold tabular">{formatMoney(d.amount, lang)}</div>
          </div>
        )}
      </div>
      <div className="mt-8 grid gap-3">
        <Link to={orderLink}>
          <Button block size="xl" data-testid="pay-back-to-order">
            {kind === "failed" ? t("patient.pay.tryAgain") : t("patient.pay.viewOrder")}
          </Button>
        </Link>
      </div>
    </Screen>
  );
}
