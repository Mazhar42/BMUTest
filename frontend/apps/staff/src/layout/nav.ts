import {
  Activity,
  Banknote,
  BarChart3,
  Beaker,
  BookOpenCheck,
  CalendarClock,
  ClipboardCheck,
  ClipboardList,
  FileCheck2,
  FileClock,
  FileSearch,
  FlaskConical,
  HandCoins,
  Home,
  HousePlus,
  IdCard,
  LayoutDashboard,
  ListOrdered,
  type LucideIcon,
  MonitorPlay,
  Printer,
  Receipt,
  ScanLine,
  ScrollText,
  Settings2,
  ShieldCheck,
  Siren,
  Stamp,
  TestTubes,
  UserPlus,
  Users,
  Wallet,
} from "lucide-react";

export interface NavItem {
  key: string;
  path: string;
  icon: LucideIcon;
  perms: string[];
  /** Roadmap milestone that builds this screen; unset = available now. */
  milestone?: number;
}

export interface NavGroup {
  key: string;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  {
    key: "overview",
    items: [{ key: "dashboard", path: "/", icon: LayoutDashboard, perms: ["self.profile"] }],
  },
  {
    key: "frontDesk",
    items: [
      { key: "helpdesk", path: "/helpdesk", icon: UserPlus, perms: ["order.create_walkin"] },
      { key: "verification", path: "/verification", icon: ClipboardCheck, perms: ["order.verify"] },
      { key: "waivers", path: "/waivers", icon: Stamp, perms: ["waiver.approve", "waiver.request"] },
      { key: "orders", path: "/orders", icon: ListOrdered, perms: ["order.view"] },
      { key: "patients", path: "/patients", icon: IdCard, perms: ["patient.search"] },
    ],
  },
  {
    key: "payments",
    items: [
      { key: "teller", path: "/teller", icon: Banknote, perms: ["payment.teller.receive"], milestone: 4 },
      { key: "cashier", path: "/cashier", icon: Wallet, perms: ["payment.counter.receive"], milestone: 4 },
      { key: "refunds", path: "/refunds", icon: HandCoins, perms: ["payment.refund.request", "payment.refund.approve"], milestone: 4 },
      { key: "reconciliation", path: "/reconciliation", icon: Receipt, perms: ["payment.reconcile"], milestone: 4 },
    ],
  },
  {
    key: "collection",
    items: [
      { key: "checkin", path: "/checkin", icon: ScanLine, perms: ["queue.checkin"], milestone: 5 },
      { key: "station", path: "/station", icon: TestTubes, perms: ["queue.call", "specimen.collect"], milestone: 6 },
      { key: "home", path: "/home-collection", icon: HousePlus, perms: ["home.manage", "home.collect"], milestone: 10 },
    ],
  },
  {
    key: "laboratory",
    items: [
      { key: "reception", path: "/lab-reception", icon: Beaker, perms: ["specimen.receive"], milestone: 6 },
      { key: "worklist", path: "/worklist", icon: FlaskConical, perms: ["result.enter"], milestone: 7 },
      { key: "release", path: "/release", icon: FileCheck2, perms: ["result.verify"], milestone: 7 },
      { key: "reportDesk", path: "/report-desk", icon: Printer, perms: ["report.deliver"], milestone: 8 },
    ],
  },
  {
    key: "admin",
    items: [
      { key: "catalog", path: "/admin/catalog", icon: BookOpenCheck, perms: ["catalog.manage"] },
      { key: "capacity", path: "/admin/capacity", icon: CalendarClock, perms: ["capacity.manage"], milestone: 5 },
      { key: "staff", path: "/admin/staff", icon: Users, perms: ["staff.manage"] },
      { key: "devices", path: "/admin/devices", icon: MonitorPlay, perms: ["device.manage"], milestone: 5 },
      { key: "downtime", path: "/admin/downtime", icon: Siren, perms: ["downtime.manage", "backentry.create"], milestone: 9 },
      { key: "settings", path: "/admin/settings", icon: Settings2, perms: ["settings.manage"], milestone: 9 },
    ],
  },
  {
    key: "oversight",
    items: [
      { key: "analytics", path: "/analytics", icon: BarChart3, perms: ["analytics.view"], milestone: 9 },
      { key: "audit", path: "/audit", icon: ScrollText, perms: ["audit.view"], milestone: 9 },
    ],
  },
];

export const EXTRA_ICONS = { Activity, FileClock, FileSearch, ClipboardList, ShieldCheck, Home };
