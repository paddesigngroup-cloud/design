import { reactive } from "vue";

const state = reactive({
  open: false,
  title: "",
  message: "",
  mode: "alert", // alert | confirm | prompt
  inputValue: "",
  confirmText: "تایید",
  cancelText: "لغو",
  _resolver: null,
});

function closeWith(value) {
  const resolver = state._resolver;
  state.open = false;
  state._resolver = null;
  if (resolver) resolver(value);
}

function ask({ title = "", message = "", mode = "alert", defaultValue = "", confirmText = "تایید", cancelText = "لغو" } = {}) {
  if (state.open && state._resolver) {
    state._resolver(mode === "prompt" ? null : false);
  }
  state.title = title;
  state.message = message;
  state.mode = mode;
  state.inputValue = defaultValue;
  state.confirmText = confirmText;
  state.cancelText = cancelText;
  state.open = true;

  return new Promise((resolve) => {
    state._resolver = resolve;
  });
}

export function useDialogService() {
  return {
    dialogState: state,
    alert(message, opts = {}) {
      return ask({ ...opts, message, mode: "alert" }).then(() => true);
    },
    confirm(message, opts = {}) {
      return ask({ ...opts, message, mode: "confirm" });
    },
    prompt(message, defaultValue = "", opts = {}) {
      return ask({ ...opts, message, mode: "prompt", defaultValue });
    },
    resolveConfirm(ok) {
      if (state.mode === "prompt") {
        closeWith(ok ? String(state.inputValue ?? "") : null);
      } else if (state.mode === "confirm") {
        closeWith(!!ok);
      } else {
        closeWith(true);
      }
    },
    close() {
      closeWith(state.mode === "prompt" ? null : false);
    },
  };
}
