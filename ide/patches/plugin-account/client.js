// The browser half: balance and free allowance, in the sidebar above Settings.
//
// Season asked for it there, and there is a slot for exactly that:
// `sidebar.footer.action` is declared by the sidebar plugin as a LIST slot and
// rendered immediately above `sidebar.settings`. Filling it is the supported
// way to put something in that spot; nothing here reaches into anyone's markup.
//
// Written in the composed form the client bundler emits — window.__ModuleLoader__
// .load({ id, factory }) with a `require` for react — rather than in JSX put
// through a build. This package ships inside the launcher's own package and has
// no build step of its own; hand-writing the output is what keeps it that way,
// and the format is small enough to read.
//
// Styling uses the app's own CSS variables, so it follows the theme instead of
// pinning colours that would be wrong in one of the two.

window.__ModuleLoader__.load({
  id: "@tokenharbor/halyard-account",
  factory: (require) => {
    var module = { exports: {} };
    var exports = module.exports;
    Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });

    const jsxRuntime = require("react/jsx-runtime");
    const react = require("react");
    const jsx = jsxRuntime.jsx;
    const jsxs = jsxRuntime.jsxs;

    const POLL_MS = 60_000;

    // Read by the model picker as it renders (see bin/rebrand.mjs). Absent
    // means off, so nothing changes for anyone who never touches the switch.
    const ORCHESTRA_KEY = "halyard.orchestra";
    const orchestraOn = () => {
      try {
        return localStorage.getItem(ORCHESTRA_KEY) === "1";
      } catch {
        return false;
      }
    };

    // Hiding in the collapsed rail is done in CSS, not in the component.
    //
    // The first attempt gated on a `wide` prop, on the strength of the sidebar
    // passing `{ wide }` to renderSlot. It does — but that is the slot's own
    // share, not necessarily this component's props, and the panel mounted,
    // fetched twice, and rendered nothing at all: `!undefined` is true, so it
    // returned null every time. Two 200s in the network log and an empty
    // sidebar is a memorable way to learn that.
    //
    // The sidebar root carries a `collapsed` class whatever the props do, so a
    // descendant rule is both simpler and true by construction. Injected the
    // way every other client plugin here injects its CSS.
    const CSS_ID = "@tokenharbor/halyard-account/panel.css";
    if (typeof document !== "undefined" && !document.querySelector(`style[data-plugin-css=${JSON.stringify(CSS_ID)}]`)) {
      const tag = document.createElement("style");
      tag.dataset.plugin = "@tokenharbor/halyard-account";
      tag.dataset.pluginCss = CSS_ID;
      tag.textContent =
        '[class*="_collapsed"] [data-halyard-account]{display:none}' +
        // The bar on the sign-in card while it waits for an approval.
        '@keyframes halyard-auth-slide{0%{transform:translateX(-100%)}100%{transform:translateX(300%)}}';
      document.head.appendChild(tag);
    }

    // Cents below a thousand, whole dollars above. The first version dropped to
    // one decimal at ten and rendered $42.17 as "$42.2", which does not read as
    // money — an amount someone is checking should look like the amount.
    const money = (n) =>
      n === null || n === undefined
        ? "—"
        : `$${n < 1000 ? n.toFixed(2) : Math.round(n).toLocaleString()}`;

    /** "resets in 3 days" — the bar means little without knowing when it lifts. */
    function resetsIn(iso) {
      if (!iso) return null;
      const ms = Date.parse(iso) - Date.now();
      if (!Number.isFinite(ms) || ms <= 0) return null;
      const hours = Math.round(ms / 3_600_000);
      if (hours < 1) return "resets within the hour";
      if (hours < 48) return `resets in ${hours}h`;
      return `resets in ${Math.round(hours / 24)}d`;
    }

    /** The account, polled. Shared by the sidebar strip and the Settings page
     *  so the two can never disagree about the same numbers. */
    function useAccount() {
      const [state, setState] = react.useState(null);

      react.useEffect(() => {
        let live = true;
        const read = async () => {
          try {
            const res = await fetch("/api/halyard/account", { cache: "no-store" });
            const body = await res.json();
            if (live) setState(body);
          } catch {
            if (live) setState({ unreachable: true });
          }
        };
        read();
        const timer = window.setInterval(read, POLL_MS);
        // And whenever the window comes back. A minute is a fine heartbeat for
        // a number that drifts slowly, and far too long for the moment somebody
        // switches back to this window specifically to see whether their
        // top-up landed. Costs one request on a focus, and the node half caches
        // for ten seconds, so clicking around cannot turn into traffic.
        const onFocus = () => read();
        window.addEventListener("focus", onFocus);
        // And whenever this TAB becomes visible, which is not the same event.
        //
        // A background tab is throttled and, after a few minutes, frozen: its
        // interval stops running entirely. `focus` fires when the WINDOW is
        // reactivated, so a tab switched away from inside one window came back
        // showing whatever it had when it went to sleep. Erika, 2026-08-18,
        // read a balance and an allowance beside the dashboard's and reported
        // them as out of sync; both were right, one was old.
        const onVisible = () => {
          if (!document.hidden) read();
        };
        document.addEventListener("visibilitychange", onVisible);
        return () => {
          live = false;
          window.clearInterval(timer);
          window.removeEventListener("focus", onFocus);
          document.removeEventListener("visibilitychange", onVisible);
        };
      }, []);

      return state;
    }

    function AccountPanel() {
      const state = useAccount();
      // Held in state so the switch moves the moment it is clicked. It also
      // listens, so a second window and this one cannot disagree about it.
      const [orchestra, setOrchestra] = react.useState(orchestraOn);
      const [funMode, setFunMode] = react.useState(false);
      react.useEffect(() => {
        fetch("/api/halyard/fun-mode")
          .then((r) => r.json())
          .then((d) => setFunMode(d.enabled === true))
          .catch(() => {});
      }, []);
      react.useEffect(() => {
        const read = () => setOrchestra(orchestraOn());
        window.addEventListener("halyard:orchestra", read);
        window.addEventListener("storage", read);
        return () => {
          window.removeEventListener("halyard:orchestra", read);
          window.removeEventListener("storage", read);
        };
      }, []);

      if (state === null) return null;
      if (state.signedIn === false) {
        return jsx("div", {
          "data-halyard-account": true,
          style: {
            width: "100%",
            boxSizing: "border-box",
            padding: "8px 8px 10px",
            borderTop: "1px solid var(--dsw-alias-border-l2)",
          },
          children: jsx("button", {
            type: "button",
            onClick: () => {
              window.dispatchEvent(new CustomEvent("halyard:open-auth"));
            },
            style: {
              display: "block",
              width: "100%",
              padding: "6px 12px",
              fontSize: "12px",
              fontWeight: 600,
              lineHeight: "18px",
              textAlign: "center",
              color: "var(--dsw-alias-bg-base)",
              background: "var(--dsw-alias-label-primary)",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
            },
            children: "Đăng nhập (Sign in)",
          }),
        });
      }

      const rowStyle = {
        display: "flex",
        alignItems: "baseline",
        justifyContent: "space-between",
        gap: "8px",
        fontSize: "12px",
        lineHeight: "18px",
      };

      const children = [];

      // 1. Nút HACK CƠ LỎ (Gắn full file deepseek-4-1.md)
      children.push(
        jsxs(
          "div",
          {
            key: "hack-mode",
            style: {
              ...rowStyle,
              alignItems: "center",
              paddingBottom: "10px",
              marginBottom: "8px",
              borderBottom: "1px solid var(--dsw-alias-border-l2)",
            },
            children: [
              jsx("span", {
                style: {
                  color: funMode ? "#10b981" : "var(--dsw-alias-label-secondary)",
                  fontWeight: funMode ? 600 : 400,
                },
                children: "HACK CƠ LỎ",
              }),
              jsx("button", {
                type: "button",
                role: "switch",
                "aria-checked": funMode,
                title: "Bật/Tắt HACK CƠ LỎ (Gắn full file md)",
                onClick: () => {
                  const next = !funMode;
                  setFunMode(next);
                  fetch(`/api/halyard/fun-mode?enabled=${next}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ enabled: next }),
                  }).catch(() => {});
                },
                style: {
                  flex: "none",
                  width: "32px",
                  height: "18px",
                  padding: "2px",
                  borderRadius: "9px",
                  border: "1px solid var(--dsw-alias-border-l2)",
                  cursor: "pointer",
                  background: funMode
                    ? "#10b981"
                    : "var(--dsw-alias-fill-l2)",
                  transition: "background .15s",
                },
                children: jsx("span", {
                  style: {
                    display: "block",
                    width: "12px",
                    height: "12px",
                    borderRadius: "6px",
                    background: "var(--dsw-alias-bg-base)",
                    transform: funMode ? "translateX(14px)" : "translateX(0)",
                    transition: "transform .15s",
                  },
                }),
              }),
            ],
          },
          "hack-mode",
        ),
      );

      // 2. Nút Orchestra
      children.push(
        jsxs(
          "div",
          {
            key: "orchestra",
            style: {
              ...rowStyle,
              alignItems: "center",
              paddingBottom: "10px",
              marginBottom: "8px",
              borderBottom: "1px solid var(--dsw-alias-border-l2)",
            },
            children: [
              jsx("span", {
                style: { color: "var(--dsw-alias-label-secondary)" },
                children: "Orchestra",
              }),
              jsx("button", {
                type: "button",
                role: "switch",
                "aria-checked": orchestra,
                title: "Route every turn through Orchestra",
                onClick: () => {
                  const next = !orchestra;
                  try {
                    if (next) localStorage.setItem(ORCHESTRA_KEY, "1");
                    else localStorage.removeItem(ORCHESTRA_KEY);
                  } catch {
                    return;
                  }
                  setOrchestra(next);
                  window.dispatchEvent(new Event("halyard:orchestra"));
                },
                style: {
                  flex: "none",
                  width: "32px",
                  height: "18px",
                  padding: "2px",
                  borderRadius: "9px",
                  border: "1px solid var(--dsw-alias-border-l2)",
                  cursor: "pointer",
                  background: orchestra
                    ? "var(--dsw-alias-label-primary)"
                    : "var(--dsw-alias-fill-l2)",
                  transition: "background .15s",
                },
                children: jsx("span", {
                  style: {
                    display: "block",
                    width: "12px",
                    height: "12px",
                    borderRadius: "6px",
                    background: "var(--dsw-alias-bg-base)",
                    transform: orchestra ? "translateX(14px)" : "translateX(0)",
                    transition: "transform .15s",
                  },
                }),
              }),
            ],
          },
          "orchestra",
        ),
      );

      children.push(
        jsxs(
          "div",
          {
            style: rowStyle,
            children: [
              jsx("span", {
                style: { color: "var(--dsw-alias-label-tertiary)" },
                children: "Balance",
              }),
              jsx("span", {
                style: {
                  color: "var(--dsw-alias-label-primary)",
                  fontVariantNumeric: "tabular-nums",
                },
                children: state.unreachable
                  ? "offline"
                  : state.balanceError
                    ? "—"
                    : money(state.balanceUsd),
              }),
            ],
          },
          "balance",
        ),
      );

      /**
       * One labelled allowance: a proportion, a bar, and when it refills.
       *
       * Shared by both pools because they are genuinely the same shape — but
       * they are drawn SEPARATELY on purpose. A pass and the free allowance are
       * different pools: a subscriber calling a free model spends the free one
       * and leaves the pass untouched, so one combined bar would misreport
       * both. Season asked whether a subscriber can see their pass here; the
       * answer is a second bar, not a bigger one.
       */
      const allowanceBar = (key, label, usedPct, exhausted, endsAt) => {
        const pct = Math.max(0, Math.min(100, usedPct));
        const reset = resetsIn(endsAt);
        const dim = exhausted
          ? "var(--dsw-alias-label-tertiary)"
          : "var(--dsw-alias-label-secondary)";
        return jsxs(
          "div",
          {
            style: { marginTop: "6px" },
            children: [
              jsxs("div", {
                style: rowStyle,
                children: [
                  jsx("span", {
                    style: { color: "var(--dsw-alias-label-tertiary)" },
                    children: label,
                  }),
                  jsx("span", {
                    style: { color: dim, fontVariantNumeric: "tabular-nums" },
                    // A proportion, never an amount. The gateway does not send
                    // one and this must not look like it knows better.
                    children: exhausted ? "used up" : `${100 - pct}% left`,
                  }),
                ],
              }),
              jsx("div", {
                style: {
                  height: "4px",
                  marginTop: "4px",
                  borderRadius: "2px",
                  overflow: "hidden",
                  background: "var(--dsw-alias-fill-l2)",
                },
                children: jsx("div", {
                  style: {
                    width: `${100 - pct}%`,
                    height: "100%",
                    borderRadius: "2px",
                    background: dim,
                    transition: "width .3s",
                  },
                }),
              }),
              reset === null
                ? null
                : jsx("div", {
                    style: {
                      marginTop: "3px",
                      fontSize: "11px",
                      color: "var(--dsw-alias-label-tertiary)",
                    },
                    children: reset,
                  }),
            ],
          },
          key,
        );
      };

      // The pass first when there is one: it is what a subscriber is spending.
      if (state.onPlan && typeof state.planUsedPct === "number") {
        children.push(
          allowanceBar(
            "plan",
            state.planName ?? "Plan",
            state.planUsedPct,
            state.planExhausted,
            state.planEndsAt,
          ),
        );
      }

      if (typeof state.freeUsedPct === "number") {
        children.push(
          allowanceBar(
            "free",
            "Free models",
            state.freeUsedPct,
            state.freeExhausted,
            state.freeResetAt,
          ),
        );
      }

      // Said here rather than left for the first message to discover. The
      // ":free" routes refuse until the account has accepted the free-model
      // terms, and the allowance bar reads untouched the whole time — a state
      // the bar alone cannot explain.
      if (state.freeUsedPct !== null && state.freeModelsEnabled === false) {
        children.push(
          jsx(
            "a",
            {
              href: "https://tokenharbor.ai/dashboard",
              target: "_blank",
              rel: "noreferrer",
              style: {
                display: "block",
                marginTop: "5px",
                fontSize: "11px",
                lineHeight: "16px",
                color: "var(--dsw-alias-label-tertiary)",
                textDecoration: "underline",
              },
              children: "Turn on free models in your dashboard",
            },
            "consent",
          ),
        );
      }

      children.push(
        jsx(
          "button",
          {
            type: "button",
            onClick: async () => {
              if (window.confirm("Bạn có chắc chắn muốn đăng xuất không?")) {
                try {
                  await fetch("/api/halyard/auth/logout", { method: "POST" });
                  window.location.reload();
                } catch (e) {
                  alert("Lỗi đăng xuất: " + (e?.message || e));
                }
              }
            },
            style: {
              display: "block",
              width: "100%",
              marginTop: "8px",
              padding: "4px 8px",
              fontSize: "11px",
              lineHeight: "16px",
              textAlign: "center",
              color: "var(--dsw-alias-label-secondary)",
              background: "var(--dsw-alias-fill-l2)",
              border: "1px solid var(--dsw-alias-border-l2)",
              borderRadius: "6px",
              cursor: "pointer",
            },
            children: "Đăng xuất (Sign out)",
          },
          "logout-sidebar",
        ),
      );

      return jsx("div", {
        "data-halyard-account": true,
        style: {
          width: "100%",
          boxSizing: "border-box",
          padding: "8px 8px 10px",
          borderTop: "1px solid var(--dsw-alias-border-l2)",
        },
        children,
      });
    }

    // ── Settings → General → Show Trajectory ─────────────────────────
    //
    // The tab list is filtered on this key (see bin/rebrand.mjs). Absent means
    // hidden, which is the default Season asked for and what every install
    // already has.
    const TRAJECTORY_KEY = "halyard.showTrajectory";

    const trajectoryOn = () => {
      try {
        return localStorage.getItem(TRAJECTORY_KEY) === "1";
      } catch {
        return false;
      }
    };

    function TrajectoryRow() {
      const [on, setOn] = react.useState(trajectoryOn);
      const toggle = () => {
        const next = !on;
        try {
          if (next) localStorage.setItem(TRAJECTORY_KEY, "1");
          else localStorage.removeItem(TRAJECTORY_KEY);
        } catch {
          /* storage denied: the switch will not stick, and saying so in a
             settings row is worse than the switch simply not moving */
          return;
        }
        setOn(next);
        // Reloaded rather than re-rendered, deliberately. The tab list is
        // rebuilt only when the view registry's version changes, and a
        // localStorage write cannot bump that — so the switch would appear to
        // do nothing until something else happened to invalidate it. A reload
        // is a second of nothing, and sessions live on the server, so it costs
        // no work. Better an honest second than a switch that lies.
        window.setTimeout(() => window.location.reload(), 120);
      };

      return jsxs("div", {
        style: {
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "16px",
          padding: "14px 0",
        },
        children: [
          jsxs("div", {
            children: [
              jsx("div", {
                style: {
                  fontSize: "14px",
                  lineHeight: "20px",
                  color: "var(--dsw-alias-label-primary)",
                },
                children: "Show Trajectory",
              }),
              jsx("div", {
                style: {
                  fontSize: "12px",
                  lineHeight: "18px",
                  color: "var(--dsw-alias-label-tertiary)",
                },
                children: "Adds a Trajectory tab beside Chat. Reloads the page.",
              }),
            ],
          }),
          jsx("button", {
            type: "button",
            role: "switch",
            "aria-checked": on,
            onClick: toggle,
            style: {
              flex: "none",
              width: "40px",
              height: "24px",
              padding: "2px",
              borderRadius: "12px",
              border: "1px solid var(--dsw-alias-border-l2)",
              cursor: "pointer",
              background: on
                ? "var(--dsw-alias-label-primary)"
                : "var(--dsw-alias-fill-l2)",
              transition: "background .15s",
            },
            children: jsx("span", {
              style: {
                display: "block",
                width: "18px",
                height: "18px",
                borderRadius: "50%",
                background: "var(--dsw-alias-bg-base)",
                transform: on ? "translateX(16px)" : "translateX(0)",
                transition: "transform .15s",
              },
            }),
          }),
        ],
      });
    }

    // ── Settings → Account ───────────────────────────────────────────
    //
    // Replaces the page we removed rather than leaving a gap. The upstream
    // Models page was a bring-your-own-key screen — "Enter your API keys to use
    // models from the following providers" — which does not belong in a
    // distribution where the models come from one account. Season chose to put
    // something of ours there instead of nothing.
    //
    // It shows what that account IS: money, pass, free allowance, and the way
    // out to the dashboard for anything that needs a real page. The same
    // numbers as the sidebar strip, from the same fetch, because two places
    // disagreeing about a balance is worse than one place not showing it.
    function AccountSection() {
      const state = useAccount();

      const row = (label, value, key) =>
        jsxs(
          "div",
          {
            style: {
              display: "flex",
              alignItems: "baseline",
              justifyContent: "space-between",
              gap: "16px",
              padding: "14px 0",
              borderBottom: "1px solid var(--dsw-alias-border-l2)",
            },
            children: [
              jsx("span", {
                style: { fontSize: "14px", color: "var(--dsw-alias-label-primary)" },
                children: label,
              }),
              jsx("span", {
                style: {
                  fontSize: "14px",
                  color: "var(--dsw-alias-label-secondary)",
                  fontVariantNumeric: "tabular-nums",
                },
                children: value,
              }),
            ],
          },
          key,
        );

      if (state === null) {
        return jsx("div", {
          style: { padding: "14px 0", color: "var(--dsw-alias-label-tertiary)" },
          children: "Loading…",
        });
      }
      if (state.signedIn === false) {
        return jsxs("div", {
          style: { padding: "16px 0" },
          children: [
            jsx("div", {
              style: { color: "var(--dsw-alias-label-tertiary)", marginBottom: "12px", fontSize: "14px" },
              children: "Bạn chưa đăng nhập vào Halyard / Token Harbor.",
            }),
            jsxs("div", {
              style: { display: "flex", gap: "10px" },
              children: [
                jsx("button", {
                  type: "button",
                  onClick: () => {
                    window.dispatchEvent(new CustomEvent("halyard:open-auth"));
                  },
                  style: {
                    padding: "8px 16px",
                    borderRadius: "10px",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                    border: "none",
                    background: "var(--dsw-alias-label-primary)",
                    color: "var(--dsw-alias-bg-base)",
                  },
                  children: "Đăng nhập (Sign in)",
                }),
                jsx("button", {
                  type: "button",
                  onClick: async () => {
                    const key = window.prompt("Nhập Token Harbor API Key (thk_live_...):");
                    if (key && key.trim()) {
                      try {
                        const r = await fetch("/api/halyard/auth/save-key", {
                          method: "POST",
                          headers: { "content-type": "application/json" },
                          body: JSON.stringify({ key: key.trim() }),
                        });
                        const b = await r.json();
                        if (b?.success) {
                          window.location.reload();
                        } else {
                          alert("Lỗi: " + (b?.error || "Không lưu được key"));
                        }
                      } catch (err) {
                        alert("Lỗi: " + err.message);
                      }
                    }
                  },
                  style: {
                    padding: "8px 16px",
                    borderRadius: "10px",
                    fontSize: "13px",
                    fontWeight: 500,
                    cursor: "pointer",
                    border: "1px solid var(--dsw-alias-border-l2)",
                    background: "transparent",
                    color: "var(--dsw-alias-label-secondary)",
                  },
                  children: "Nhập API Key thủ công",
                }),
              ],
            }),
          ],
        });
      }

      const pct = (v) => (typeof v === "number" ? `${100 - Math.max(0, Math.min(100, v))}% left` : "—");
      // Whose account, and how old the numbers are.
      //
      // Erika, 2026-08-18, put this panel beside the dashboard and reported
      // that they disagreed. They did — about the balance, the allowance and
      // the free-model switch — and both were right: the dashboard is drawn
      // once when the page loads and never again, and this panel had been in a
      // background tab the browser had frozen. Neither said which account it
      // was showing or when it had last looked, which is why a difference read
      // as a fault rather than as two clocks.
      const rows = [];
      if (state.accountEmail) rows.push(row("Account", state.accountEmail, "who"));
      rows.push(
        row("Balance", state.unreachable ? "offline" : money(state.balanceUsd), "bal"),
      );
      if (state.onPlan) {
        rows.push(row(state.planName ?? "Plan", pct(state.planUsedPct), "plan"));
        const reset = resetsIn(state.planEndsAt);
        if (reset) rows.push(row("Renews", reset, "plan-reset"));
      }
      if (typeof state.freeUsedPct === "number") {
        rows.push(row("Free models", state.freeExhausted ? "used up" : pct(state.freeUsedPct), "free"));
        const reset = resetsIn(state.freeResetAt);
        if (reset) rows.push(row("Free allowance resets", reset, "free-reset"));
        rows.push(
          row(
            "Free models enabled",
            state.freeModelsEnabled ? "yes" : "no — turn on in your dashboard",
            "consent",
          ),
        );
      }

      // How old these numbers are, in words, so the reader never has to guess
      // whether they are looking at a stale panel.
      const age = (() => {
        if (typeof state.readAt !== "number") return null;
        const secs = Math.max(0, Math.round((Date.now() - state.readAt) / 1000));
        if (secs < 90) return `read ${secs}s ago`;
        const mins = Math.round(secs / 60);
        if (mins < 90) return `read ${mins} min ago`;
        return `read ${Math.round(mins / 60)}h ago`;
      })();

      return jsxs("div", {
        children: [
          ...rows,
          age
            ? jsx("div", {
                style: {
                  paddingTop: "10px",
                  fontSize: "12px",
                  color: "var(--dsw-alias-label-tertiary)",
                },
                children: age,
              })
            : null,
          jsxs("div", {
            style: { display: "flex", gap: "10px", paddingTop: "16px" },
            children: [
              jsx("a", {
                href: "https://tokenharbor.ai/dashboard",
                target: "_blank",
                rel: "noreferrer",
                style: {
                  fontSize: "13px",
                  color: "var(--dsw-alias-label-secondary)",
                  textDecoration: "underline",
                },
                children: "Open dashboard",
              }),
              jsx("a", {
                href: "https://tokenharbor.ai/dashboard/billing",
                target: "_blank",
                rel: "noreferrer",
                style: {
                  fontSize: "13px",
                  color: "var(--dsw-alias-label-secondary)",
                  textDecoration: "underline",
                },
                children: "Top up",
              }),
              jsx("button", {
                type: "button",
                onClick: async () => {
                  if (window.confirm("Bạn có chắc chắn muốn đăng xuất không?")) {
                    try {
                      await fetch("/api/halyard/auth/logout", { method: "POST" });
                      window.location.reload();
                    } catch (e) {
                      alert("Lỗi đăng xuất: " + (e?.message || e));
                    }
                  }
                },
                style: {
                  fontSize: "13px",
                  color: "#ff4d4f",
                  background: "transparent",
                  border: "none",
                  padding: 0,
                  cursor: "pointer",
                  textDecoration: "underline",
                },
                children: "Đăng xuất (Sign out)",
              }),
            ],
          }),
        ],
      });
    }

    // ── Settings → Orchestra ─────────────────────────────────────────
    //
    // Rendered from a description, not from fields this file knows about.
    //
    // Season wants a change made on the website to show up here without anyone
    // updating the client. That rules out named fields: a client that knows
    // "planner, coder, frontend" needs a release the day a role is added. So
    // the gateway sends sections of items — id, label, value, source — and this
    // draws whatever arrives. It recognises nothing, which is exactly why a
    // role added tomorrow appears in a copy installed today.
    //
    // Read-only, and it says where to change them. The dashboard has the
    // catalogue, the validation and the save path; a second way to write one
    // setting is a way for two answers to exist.
    function OrchestraSection() {
      const [data, setData] = react.useState(null);

      react.useEffect(() => {
        let live = true;
        fetch("/api/halyard/orchestra", { cache: "no-store" })
          .then((r) => r.json())
          .then((b) => live && setData(b))
          .catch(() => live && setData({ unreachable: true }));
        return () => {
          live = false;
        };
      }, []);

      const note = (text) =>
        jsx("div", {
          style: { padding: "14px 0", color: "var(--dsw-alias-label-tertiary)" },
          children: text,
        });

      if (data === null) return note("Loading…");
      if (data.unreachable) return note("Could not reach Token Harbor.");
      const sections = Array.isArray(data.sections) ? data.sections : [];
      if (sections.length === 0) return note("No Orchestra settings yet.");

      return jsxs("div", {
        children: [
          ...sections.map((section) =>
            jsxs(
              "div",
              {
                style: { paddingTop: "8px" },
                children: [
                  jsx("div", {
                    style: {
                      fontSize: "12px",
                      color: "var(--dsw-alias-label-tertiary)",
                      padding: "10px 0 4px",
                    },
                    children: section.title ?? section.id,
                  }),
                  ...(Array.isArray(section.items) ? section.items : []).map((item) =>
                    jsxs(
                      "div",
                      {
                        style: {
                          display: "flex",
                          alignItems: "baseline",
                          justifyContent: "space-between",
                          gap: "16px",
                          padding: "10px 0",
                          borderBottom: "1px solid var(--dsw-alias-border-l2)",
                        },
                        children: [
                          jsx("span", {
                            style: {
                              fontSize: "14px",
                              color: "var(--dsw-alias-label-primary)",
                            },
                            children: item.label ?? item.id,
                          }),
                          jsxs("span", {
                            style: {
                              fontSize: "13px",
                              color: "var(--dsw-alias-label-secondary)",
                              display: "flex",
                              alignItems: "baseline",
                              gap: "8px",
                            },
                            children: [
                              jsx("span", { children: item.value ?? "—" }),
                              // "default" is worth saying: it is the difference
                              // between a choice someone made and one made for
                              // them, and the value alone cannot tell you which.
                              item.source === "default"
                                ? jsx("span", {
                                    style: {
                                      fontSize: "11px",
                                      color: "var(--dsw-alias-label-tertiary)",
                                    },
                                    children: "default",
                                  })
                                : null,
                            ],
                          }),
                        ],
                      },
                      item.id,
                    ),
                  ),
                ],
              },
              section.id,
            ),
          ),
          jsx("a", {
            href: data.manageUrl ?? "https://tokenharbor.ai/dashboard/orchestra",
            target: "_blank",
            rel: "noreferrer",
            style: {
              display: "inline-block",
              marginTop: "16px",
              fontSize: "13px",
              color: "var(--dsw-alias-label-secondary)",
              textDecoration: "underline",
            },
            children: "Change these in your dashboard",
          }),
        ],
      });
    }

    // ── Version, updates, and the banner ─────────────────────────────
    //
    // Season: a banner when there is a new version, the current version in the
    // corner of Settings, and after the app restarts itself the page has to say
    // to reload.
    //
    // That last part is the one with a real constraint behind it. Updating
    // stops the service this page is talking to and starts another; the page
    // survives, its socket does not, and everything it shows from then on is
    // from before. A page that looks fine and is stale is worse than one that
    // says so.
    //
    // Neither the banner nor the version line has a slot to live in — the
    // shipped slots are all inside the conversation or inside Settings — so
    // both are our own elements. The banner is fixed to the viewport, which
    // needs nobody's layout to cooperate; the version line is attached to the
    // Settings nav by finding OUR OWN nav entry and using its parent, which is
    // stable because we are the ones who put that entry there.
    let updateState = null;
    const updateListeners = new Set();
    const setUpdate = (next) => {
      updateState = next;
      for (const fn of updateListeners) fn();
    };

    async function readVersion() {
      try {
        const res = await fetch("/api/halyard/version", { cache: "no-store" });
        return await res.json();
      } catch {
        return null;
      }
    }

    /**
     * Wait for the service to come back after it has been replaced.
     *
     * Polls rather than assumes a duration: an upgrade is a download and an
     * install, and how long that takes is a fact about somebody's connection.
     * Gives up after five minutes and says so, because a spinner that never
     * ends is a lie told slowly.
     */
    async function awaitRestart() {
      const deadline = Date.now() + 300_000;
      // It has to go DOWN first, or the first successful poll is the service
      // that is about to be stopped and the banner declares victory early.
      let sawDown = false;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 2000));
        const v = await readVersion();
        if (v === null) {
          sawDown = true;
          continue;
        }
        if (sawDown) return v;
      }
      return null;
    }

    function UpdateBanner() {
      return null; // Update banner disabled
      const [, bump] = react.useReducer((n) => n + 1, 0);

      react.useEffect(() => {
        updateListeners.add(bump);
        let live = true;
        const check = async () => {
          const v = await readVersion();
          if (!live || !v) return;
          // Never step on a running update with a routine poll.
          if (updateState && updateState.phase !== "available") return;
          setUpdate(v.updateAvailable ? { phase: "available", version: v.latest } : null);
        };
        check();
        // Half-hourly, plus whenever the window comes back. A version is not a
        // number anyone needs to the second.
        const timer = window.setInterval(check, 1_800_000);
        window.addEventListener("focus", check);
        return () => {
          live = false;
          updateListeners.delete(bump);
          window.clearInterval(timer);
          window.removeEventListener("focus", check);
        };
      }, []);

      if (updateState === null) return null;

      const bar = (children) =>
        jsx("div", {
          style: {
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 2147483000,
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: "12px",
            padding: "8px 14px",
            fontSize: "13px",
            background: "var(--dsw-alias-fill-l2)",
            borderBottom: "1px solid var(--dsw-alias-border-l2)",
            color: "var(--dsw-alias-label-primary)",
          },
          children,
        });

      const button = (label, onClick, strong) =>
        jsx("button", {
          type: "button",
          onClick,
          style: {
            border: strong ? "none" : "1px solid var(--dsw-alias-border-l2)",
            background: strong ? "var(--dsw-alias-label-primary)" : "transparent",
            color: strong ? "var(--dsw-alias-bg-base)" : "var(--dsw-alias-label-secondary)",
            borderRadius: "7px",
            padding: "3px 11px",
            fontSize: "12px",
            cursor: "pointer",
          },
          children: label,
        });

      if (updateState.phase === "available") {
        return bar([
          jsx("span", { key: "t", children: `New version ${updateState.version} available` }),
          button(
            "Update now",
            async () => {
              setUpdate({ phase: "updating" });
              try {
                await fetch("/api/halyard/update", { method: "POST" });
              } catch {
                /* the request dying IS the service stopping; keep waiting */
              }
              const back = await awaitRestart();
              setUpdate(
                back
                  ? { phase: "done", version: back.current ?? null }
                  : { phase: "stuck" },
              );
            },
            true,
          ),
          button("Later", () => setUpdate(null)),
        ]);
      }

      if (updateState.phase === "updating") {
        return bar([
          jsx("span", { key: "t", children: "Updating Halyard… it will restart itself." }),
        ]);
      }

      if (updateState.phase === "stuck") {
        return bar([
          jsx("span", { key: "t", children: "The update is taking longer than expected." }),
          button("Reload the page", () => window.location.reload()),
        ]);
      }

      // done
      //
      // The version is only named when the service that came back actually said
      // one. It may not: an upgrade can land a build that predates this
      // endpoint, and "Updated to undefined" would be a worse sentence than the
      // one without a number in it. Measured, not guarded against in theory —
      // the first end-to-end run of this upgraded into exactly that build.
      return bar([
        jsx("span", {
          key: "t",
          children: updateState.version
            ? `Updated to ${updateState.version}. Please reload the page.`
            : "Updated. Please reload the page.",
        }),
        button("Reload the page", () => window.location.reload(), true),
      ]);
    }

    /**
     * The version, in the bottom-left of the Settings dialog.
     *
     * Attached to the nav column by finding our own "Account" entry and walking
     * up to its list — our entry, so the anchor is one we control rather than a
     * class name that belongs to somebody else and can be regenerated.
     */
    function mountVersionLabel() {
      if (typeof document === "undefined") return;
      const ID = "halyard-version-label";

      const place = async () => {
        const existing = document.getElementById(ID);
        const nav = [...document.querySelectorAll("button")]
          .find((b) => (b.textContent || "").trim() === "Account")?.parentElement;
        if (!nav) {
          existing?.remove();
          return;
        }
        if (existing && nav.contains(existing)) return;
        const v = await readVersion();
        if (!v?.current) return;
        if (document.getElementById(ID)) return;
        const el = document.createElement("div");
        el.id = ID;
        el.style.cssText =
          "margin-top:auto;padding:10px 4px 2px;font-size:11px;opacity:.45;" +
          "color:var(--dsw-alias-label-tertiary)";
        el.textContent =
          v.channel === "preview" ? `${v.current} · preview` : `${v.current}`;
        nav.appendChild(el);
        // The nav is a column; without this the label sits under the last item
        // rather than at the bottom of it.
        try {
          const s = getComputedStyle(nav);
          if (s.display === "flex" && s.flexDirection === "column") {
            nav.style.height = nav.style.height || "100%";
          }
        } catch {
          /* styling is a nicety; the text is the point */
        }
      };

      // The dialog is created and destroyed as it opens and closes, so this
      // watches rather than runs once.
      const observer = new MutationObserver(() => {
        place();
      });
      observer.observe(document.body, { childList: true, subtree: true });
      place();
    }

    // ── Web search: a switch, and an offer when it is wanted ─────────
    //
    // Season: it must be turned on in Settings, and when something tries to
    // search while it is off the reader should be asked — with the price —
    // rather than left with a model quietly answering from memory.
    //
    // The preference lives in a file on the service, not in this page: the
    // thing that searches runs there and cannot read localStorage. So this
    // reads and writes it over the same local API as everything else.
    let searchPref = null;
    const searchListeners = new Set();
    const notifySearch = () => {
      for (const fn of searchListeners) fn();
    };

    async function readSearchPref() {
      try {
        const res = await fetch("/api/halyard/search-pref", { cache: "no-store" });
        searchPref = await res.json();
      } catch {
        /* leave the last known answer rather than flapping the switch */
      }
      notifySearch();
      return searchPref;
    }

    async function writeSearchPref(enabled) {
      try {
        const res = await fetch("/api/halyard/search-pref", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ enabled }),
        });
        searchPref = await res.json();
      } catch {
        /* a failed write leaves the switch where it was, which is honest */
      }
      notifySearch();
    }

    function useSearchPref() {
      const [, bump] = react.useReducer((n) => n + 1, 0);
      react.useEffect(() => {
        searchListeners.add(bump);
        readSearchPref();
        // Polled, because the thing that changes it is a search happening on
        // the other side of this connection — not a click in this page.
        const timer = window.setInterval(readSearchPref, 5000);
        return () => {
          searchListeners.delete(bump);
          window.clearInterval(timer);
        };
      }, []);
      return searchPref;
    }

    const priceText = (p) =>
      `about $${(p?.priceUsd ?? 0.006).toFixed(3)} per search, charged to your pass or balance`;

    function SearchRow() {
      const pref = useSearchPref();
      const on = pref?.enabled === true;
      return jsxs("div", {
        style: {
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "16px",
          padding: "14px 0",
        },
        children: [
          jsxs("div", {
            children: [
              jsx("div", {
                style: {
                  fontSize: "14px",
                  lineHeight: "20px",
                  color: "var(--dsw-alias-label-primary)",
                },
                children: "Web search",
              }),
              jsx("div", {
                style: {
                  fontSize: "12px",
                  lineHeight: "18px",
                  color: "var(--dsw-alias-label-tertiary)",
                },
                children: `Lets the agent search the web — ${priceText(pref)}.`,
              }),
            ],
          }),
          jsx("button", {
            type: "button",
            role: "switch",
            "aria-checked": on,
            onClick: () => writeSearchPref(!on),
            style: {
              flex: "none",
              width: "40px",
              height: "24px",
              padding: "2px",
              borderRadius: "12px",
              border: "1px solid var(--dsw-alias-border-l2)",
              cursor: "pointer",
              background: on
                ? "var(--dsw-alias-label-primary)"
                : "var(--dsw-alias-fill-l2)",
              transition: "background .15s",
            },
            children: jsx("span", {
              style: {
                display: "block",
                width: "18px",
                height: "18px",
                borderRadius: "50%",
                background: "var(--dsw-alias-bg-base)",
                transform: on ? "translateX(16px)" : "translateX(0)",
                transition: "transform .15s",
              },
            }),
          }),
        ],
      });
    }

    /**
     * Offered at the moment somebody wanted a search, not in a settings page
     * they would have to already know to open.
     *
     * The service records WHEN a search was refused; this shows the offer while
     * that is recent. Recency matters: a refusal from an hour ago is not a
     * question anybody is still waiting on the answer to.
     */
    // The mark and the name, in the slots the sidebar declares for them.
    //
    // Season, 2026-08-21: "修复左上角3个tokenharbor icon和1个鲸鱼还有重叠的字体
    // （这个你修了好几遍没有根治）". He is right that it was never rooted out. It
    // was done in CSS — hide their svg, paint ours through a mask on
    // [class*="_brand"] — and the sidebar's markup moved underneath it:
    //
    //     <button class="…_brand">
    //       <span class="…_brandIdentity">
    //         <span class="…_brandMark">{slot | <FishLogo/>}</span>
    //         <span class="…_brandName">{slot | "DSH Local Build"}</span>
    //
    // Four nested elements whose class contains "_brand", so the selector
    // matched all four and drew four marks and four names; and the whale moved
    // one level down, out of reach of a `> svg` rule, so it stayed. Three icons
    // and a fish, exactly as photographed.
    //
    // The harness declares slots for both of these. Filling them means the
    // FishLogo fallback is never rendered — the whale is not hidden, it does
    // not exist — and nothing here depends on a class name that the next
    // release is free to change.
    const MARK_PATHS = [
          "M10170 16714 c-60 -20 -118 -55 -290 -176 -483 -338 -1136 -761 -1605 -1040 -115 -69 -255 -151 -309 -184 -144 -86 -139 -71 -132 -379 3 -137 6 -317 6 -398 0 -144 1 -149 25 -172 16 -17 35 -25 57 -24 18 0 380 127 803 283 424 156 773 281 778 279 4 -2 7 -1067 7 -2367 l0 -2363 23 -20 c59 -55 34 -53 731 -53 l645 0 28 24 28 24 3 2386 c1 1312 6 2386 10 2386 8 0 70 -23 1015 -369 302 -111 562 -201 578 -201 18 0 39 10 54 25 24 23 25 29 25 167 0 79 3 257 7 395 8 352 34 306 -275 490 -618 367 -1203 744 -1727 1113 -196 138 -220 153 -303 181 -71 24 -91 24 -182 -7z",
          "M14363 14346 l-28 -24 -6 -2219 c-6 -2386 -3 -2262 -55 -2568 -206 -1210 -902 -2256 -1979 -2972 -349 -232 -758 -437 -1163 -582 -78 -28 -147 -51 -152 -51 -6 0 -11 430 -12 1196 l-3 1196 -28 24 -28 24 -645 0 c-697 0 -672 2 -731 -53 l-23 -20 0 -1203 c0 -662 -3 -1205 -7 -1207 -5 -3 -87 25 -183 63 -592 229 -1105 519 -1560 884 -293 235 -612 560 -814 831 -486 650 -741 1334 -775 2075 -4 91 -9 1157 -9 2370 l-2 2205 -26 23 c-14 12 -31 22 -39 22 -7 0 -82 -29 -167 -64 -347 -144 -714 -282 -1003 -376 -149 -49 -171 -62 -201 -122 l-26 -51 5 -891 c5 -918 10 -1075 57 -1701 108 -1419 278 -2162 671 -2932 185 -363 397 -686 723 -1103 151 -192 200 -246 345 -373 463 -408 910 -710 1821 -1232 934 -535 1339 -812 1770 -1206 132 -121 135 -124 181 -124 44 0 50 3 137 86 269 256 617 522 1012 771 215 136 352 217 835 495 429 247 608 354 830 496 364 234 746 524 1029 781 190 173 640 780 856 1156 40 69 118 220 175 335 360 732 523 1455 625 2765 19 251 20 331 18 1502 l-3 1237 -30 31 c-39 41 -56 50 -205 100 -310 105 -743 270 -1027 391 -51 21 -101 39 -112 39 -11 0 -33 -11 -48 -24z"
    ];

    function BrandMark(props) {
      const size = (props && props.size) || 24;
      return jsx("svg", {
        width: size,
        height: size,
        viewBox: "0 0 2048 2048",
        role: "img",
        "aria-label": "Halyard",
        style: { display: "block" },
        children: jsx("g", {
          transform: "translate(0,2048) scale(0.1,-0.1)",
          fill: "currentColor",
          stroke: "none",
          children: MARK_PATHS.map((d, i) => jsx("path", { d: d }, "p" + i)),
        }),
      });
    }

    function BrandName() {
      return jsx("span", {
        style: {
          fontSize: "17px",
          fontWeight: 700,
          letterSpacing: "-0.01em",
          lineHeight: 1,
          whiteSpace: "nowrap",
        },
        children: "Halyard",
      });
    }

    // Signing in, in the page.
    //
    // Season, 2026-08-21: "现在是软件弹框auth，我要改成网页Halyard弹框auth." It
    // was a window the app put in front of the browser; it belongs where the
    // reader already is. Three states in one card — ask, wait, done — and the
    // key never comes near this code: the service does the asking and the
    // storing, and this only draws what it is told.
    function AuthModal() {
      const [state, setState] = react.useState("checking");
      const [session, setSession] = react.useState("");
      const [why, setWhy] = react.useState("");

      react.useEffect(() => {
        const onOpen = () => {
          setState("ask");
          setWhy("");
        };
        window.addEventListener("halyard:open-auth", onOpen);
        return () => window.removeEventListener("halyard:open-auth", onOpen);
      }, []);

      react.useEffect(() => {
        let alive = true;
        fetch("/api/halyard/auth", { cache: "no-store" })
          .then((r) => r.json())
          .then((b) => { if (alive) setState(b?.signedIn ? "done-quietly" : "ask"); })
          .catch(() => { if (alive) setState("done-quietly"); });
        return () => { alive = false; };
      }, []);

      react.useEffect(() => {
        if (state !== "waiting" || !session) return;
        let alive = true;
        const started = Date.now();
        const tick = async () => {
          if (!alive) return;
          try {
            const r = await fetch(
              "/api/halyard/auth/poll?session=" + encodeURIComponent(session),
              { cache: "no-store" },
            );
            const b = await r.json();
            if (!alive) return;
            if (b?.signedIn) { setState("in"); return; }
            if (b?.status === "denied") { setState("ask"); setWhy("That sign-in was declined."); return; }
            if (b?.status === "expired" || b?.status === "not_found") {
              setState("ask"); setWhy("That link expired — they last five minutes."); return;
            }
          } catch {
            /* a blip; keep asking */
          }
          if (Date.now() - started > 5 * 60_000) {
            setState("ask");
            setWhy("Nobody approved it within five minutes.");
            return;
          }
          setTimeout(tick, Date.now() - started < 30_000 ? 900 : 2000);
        };
        setTimeout(tick, 700);
        return () => { alive = false; };
      }, [state, session]);

      // Gone once it is done, after a beat on the good news, then reload.
      react.useEffect(() => {
        if (state !== "in") return;
        const t = setTimeout(() => {
          setState("done-quietly");
          window.location.reload();
        }, 1500);
        return () => clearTimeout(t);
      }, [state]);

      if (state === "checking" || state === "done-quietly") return null;

      const begin = async () => {
        setWhy("");
        setState("starting");
        try {
          const r = await fetch("/api/halyard/auth/start", { method: "POST" });
          const b = await r.json();
          if (!r.ok || !b?.url) throw new Error(b?.error || "the gateway sent no link");
          setSession(b.session);
          setState("waiting");
          window.open(b.url, "_blank", "noopener");
        } catch (e) {
          setState("ask");
          setWhy(String((e && e.message) || e));
        }
      };

      const card = {
        width: "min(440px, calc(100vw - 48px))",
        padding: "22px 24px 18px",
        borderRadius: "16px",
        background: "var(--dsw-alias-bg-base)",
        border: "1px solid var(--dsw-alias-border-l2)",
        boxShadow: "var(--dsw-shadow-lv3)",
        color: "var(--dsw-alias-label-primary)",
        fontSize: "14px",
        lineHeight: "1.55",
      };

      const button = (label, onClick, primary) =>
        jsx("button", {
          type: "button",
          onClick: onClick,
          style: {
            padding: "8px 16px",
            borderRadius: "10px",
            fontSize: "13px",
            fontWeight: 600,
            cursor: "pointer",
            border: primary ? "none" : "1px solid var(--dsw-alias-border-l2)",
            background: primary ? "var(--dsw-alias-label-primary)" : "transparent",
            color: primary ? "var(--dsw-alias-bg-base)" : "var(--dsw-alias-label-secondary)",
          },
          children: label,
        });

      const heading =
        state === "in" ? "You're in"
        : state === "waiting" || state === "starting" ? "Approve it in your browser"
        : "Connect your Token Harbor account";

      const line =
        state === "in" ? "Enjoy Halyard."
        : state === "starting" ? "Asking for a link…"
        : state === "waiting" ? "A tab has opened. Click Approve there — this page notices by itself."
        : "Halyard runs either way. The Token Harbor models need your account before they will answer.";

      return jsx("div", {
        style: {
          position: "fixed",
          inset: 0,
          zIndex: 2147483100,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "rgba(15, 18, 24, 0.38)",
          backdropFilter: "blur(2px)",
        },
        children: jsxs("div", {
          style: card,
          children: [
            jsxs("div", {
              style: { display: "flex", alignItems: "center", gap: "12px", marginBottom: "10px" },
              children: [
                jsx(BrandMark, { size: 28 }),
                jsx("div", {
                  style: { fontSize: "17px", fontWeight: 700, letterSpacing: "-0.01em" },
                  children: heading,
                }),
              ],
            }),
            jsx("div", {
              style: { color: "var(--dsw-alias-label-secondary)", minHeight: "44px" },
              children: line,
            }),
            why
              ? jsx("div", {
                  style: { marginTop: "6px", color: "var(--dsw-alias-status-error, #c0392b)", fontSize: "13px" },
                  children: why,
                })
              : null,
            state === "waiting" || state === "starting"
              ? jsx("div", {
                  style: {
                    height: "3px",
                    marginTop: "14px",
                    borderRadius: "3px",
                    background: "var(--dsw-alias-border-l2)",
                    overflow: "hidden",
                  },
                  children: jsx("div", {
                    style: {
                      width: "38%",
                      height: "100%",
                      borderRadius: "3px",
                      background: "var(--dsw-alias-label-primary)",
                      animation: "halyard-auth-slide 1.1s ease-in-out infinite",
                    },
                  }),
                })
              : null,
            state === "ask"
              ? jsxs("div", {
                  style: { display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "16px" },
                  children: [
                    button("Not now", () => setState("done-quietly"), false),
                    button("Nhập Key", async () => {
                      const key = window.prompt("Nhập Token Harbor API Key (thk_live_...):");
                      if (key && key.trim()) {
                        try {
                          const r = await fetch("/api/halyard/auth/save-key", {
                            method: "POST",
                            headers: { "content-type": "application/json" },
                            body: JSON.stringify({ key: key.trim() }),
                          });
                          const b = await r.json();
                          if (b?.success) {
                            setState("in");
                          } else {
                            alert("Lỗi: " + (b?.error || "Không thể lưu key"));
                          }
                        } catch (err) {
                          alert("Lỗi: " + err.message);
                        }
                      }
                    }, false),
                    button("Đăng nhập (Sign in)", begin, true),
                  ],
                })
              : null,
          ],
        }),
      });
    }

    function SearchPrompt() {
      const pref = useSearchPref();
      const [dismissed, setDismissed] = react.useState(0);
      if (!pref || pref.enabled) return null;
      const blocked = pref.blockedAt ?? 0;
      if (!blocked || Date.now() - blocked > 120_000) return null;
      if (dismissed >= blocked) return null;

      return jsx("div", {
        style: {
          position: "fixed",
          left: "50%",
          transform: "translateX(-50%)",
          bottom: "24px",
          zIndex: 2147483000,
          maxWidth: "420px",
          padding: "12px 14px",
          borderRadius: "12px",
          border: "1px solid var(--dsw-alias-border-l2)",
          background: "var(--dsw-alias-bg-base)",
          boxShadow: "var(--dsw-shadow-lv3)",
          fontSize: "13px",
          lineHeight: "1.5",
          color: "var(--dsw-alias-label-primary)",
        },
        children: jsxs("div", {
          children: [
            jsx("div", {
              style: { marginBottom: "4px", fontWeight: 600 },
              children: "Turn on web search?",
            }),
            jsx("div", {
              style: {
                marginBottom: "10px",
                color: "var(--dsw-alias-label-tertiary)",
              },
              children: `The agent just tried to search the web. It is off — ${priceText(pref)}.`,
            }),
            jsxs("div", {
              style: { display: "flex", gap: "8px" },
              children: [
                jsx("button", {
                  type: "button",
                  onClick: () => writeSearchPref(true),
                  style: {
                    border: "none",
                    background: "var(--dsw-alias-label-primary)",
                    color: "var(--dsw-alias-bg-base)",
                    borderRadius: "7px",
                    padding: "4px 12px",
                    fontSize: "12px",
                    cursor: "pointer",
                  },
                  children: "Turn on",
                }),
                jsx("button", {
                  type: "button",
                  onClick: () => setDismissed(blocked),
                  style: {
                    border: "1px solid var(--dsw-alias-border-l2)",
                    background: "transparent",
                    color: "var(--dsw-alias-label-secondary)",
                    borderRadius: "7px",
                    padding: "4px 12px",
                    fontSize: "12px",
                    cursor: "pointer",
                  },
                  children: "Not now",
                }),
              ],
            }),
          ],
        }),
      });
    }

    const inject = ["slots"];

    function apply(ctx) {
      ctx.effect(
        () =>
          ctx.slots.inject("settings.general.item", () =>
            ctx.slots.register(
              {
                name: "settings.general.item",
                id: "halyard-trajectory",
                // After the rows the app ships, so an addition of ours does not
                // push their settings down the page.
                order: 90,
                inject: () => ({}),
              },
              TrajectoryRow,
            ),
          ),
        "halyard-account: trajectory switch",
      );

      ctx.effect(
        () =>
          ctx.slots.inject("settings.general.item", () =>
            ctx.slots.register(
              {
                name: "settings.general.item",
                id: "halyard-search",
                order: 88,
                inject: () => ({}),
              },
              SearchRow,
            ),
          ),
        "halyard-account: search switch",
      );

      // Where the Models page used to be. order 5 puts it above General, since
      // it is the one a person opens Settings to look at.
      ctx.effect(
        () =>
          ctx.slots.inject("settings.section", () =>
            ctx.slots.register(
              {
                name: "settings.section",
                id: "halyard-account",
                order: 5,
                label: () => "Account",
                inject: () => ({}),
              },
              AccountSection,
            ),
          ),
        "halyard-account: settings section",
      );

      ctx.effect(
        () =>
          ctx.slots.inject("settings.section", () =>
            ctx.slots.register(
              {
                name: "settings.section",
                id: "halyard-orchestra",
                order: 6,
                label: () => "Orchestra",
                inject: () => ({}),
              },
              OrchestraSection,
            ),
          ),
        "halyard-account: orchestra section",
      );

      // The sign-in card, in a slot we are already allowed to render into; it
      // positions itself over the page.
      ctx.effect(
        () =>
          ctx.slots.inject("sidebar.footer.action", () =>
            ctx.slots.register(
              { name: "sidebar.footer.action", id: "halyard-auth", order: 0, inject: () => ({}) },
              AuthModal,
            ),
          ),
        "halyard-account: sign-in card",
      );

      // The brand, in the three places the harness asks for one.
      for (const seat of [
        { slot: "sidebar.brand.mark", id: "halyard-brand-mark", body: BrandMark },
        { slot: "sidebar.brand.name", id: "halyard-brand-name", body: BrandName },
        { slot: "conversation.hero.brand.mark", id: "halyard-hero-mark", body: BrandMark },
      ]) {
        ctx.effect(
          () =>
            ctx.slots.inject(seat.slot, () =>
              ctx.slots.register(
                // priority, not order — and BELOW zero.
                //
                // These are single slots, not lists: the sidebar registers its
                // own fallback at priority 0, and a second registration at the
                // same priority is refused outright — "single slot
                // sidebar.brand.mark already has a registration at priority 0
                // … register at a different priority to shadow it (lowest
                // renders)". `order` is the list-slot word and was ignored, so
                // ours landed at 0 and collided, and the whole plugin failed to
                // load. Minus one shadows theirs.
                { name: seat.slot, id: seat.id, priority: -1, inject: () => ({}) },
                seat.body,
              ),
            ),
          "halyard-account: " + seat.id,
        );
      }

      // The banner rides in the sidebar's list slot because that is a place we
      // are already allowed to render — the element itself is fixed to the
      // viewport, so where it is mounted decides nothing about where it appears.
      ctx.effect(
        () =>
          ctx.slots.inject("sidebar.footer.action", () =>
            ctx.slots.register(
              {
                name: "sidebar.footer.action",
                id: "halyard-update-banner",
                order: 1,
                inject: () => ({}),
              },
              UpdateBanner,
            ),
          ),
        "halyard-account: update banner",
      );

      // Same reasoning as the banner: mounted in a slot we are allowed to
      // render into, positioned by its own styles.
      ctx.effect(
        () =>
          ctx.slots.inject("sidebar.footer.action", () =>
            ctx.slots.register(
              {
                name: "sidebar.footer.action",
                id: "halyard-search-prompt",
                order: 2,
                inject: () => ({}),
              },
              SearchPrompt,
            ),
          ),
        "halyard-account: search prompt",
      );

      mountVersionLabel();
      ctx.effect(
        () =>
          ctx.slots.inject("sidebar.footer.action", () =>
            ctx.slots.register(
              {
                name: "sidebar.footer.action",
                id: "halyard-account",
                inject: () => ({}),
              },
              AccountPanel,
            ),
          ),
        "halyard-account: slot registration",
      );
    }

    exports.apply = apply;
    exports.inject = inject;
    return module.exports;
  },
});
