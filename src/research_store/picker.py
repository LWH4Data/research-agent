from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


_UI_TEXT = {
    "ko": {
        "picker_prompt": (
            "목록에 추가할 폴더를 선택하세요.\n"
            "⌘ Command 키를 누른 채 클릭하면 여러 폴더를 고를 수 있습니다.\n"
            "선택한 뒤 목록에서 확인하면 PDF 저장과 시각 검토를 시작합니다."
        ),
        "onboarding_message": (
            "Research Agent 설치가 완료됐어요.\n\n"
            "지금 폴더를 연결하고 PDF 저장과 시각 검토를 시작할까요?\n"
            "원본 파일은 수정하지 않습니다."
        ),
        "later": "나중에 하기",
        "choose": "폴더 선택하기",
        "onboarding_open_error": "폴더 연결 안내창을 열 수 없습니다.",
        "onboarding_response_error": "폴더 연결 안내창의 응답을 확인할 수 없습니다.",
        "activation_error": "폴더 선택창의 앱을 활성화할 수 없습니다.",
        "add_to_list": "목록에 추가",
        "picker_response_error": "폴더 선택창이 선택을 완료하지 못했습니다.",
        "local_folders_error": "로컬 폴더만 선택할 수 있습니다.",
        "selection_title": "연결할 폴더",
        "selection_message": "확인하면 선택한 폴더의 PDF를 저장하고 시각 검토를 시작합니다. 원본 파일은 수정하지 않습니다.",
        "connect": "연결하고 PDF 저장하기",
        "add": "폴더 추가하기",
        "add_more": "폴더 더 추가하기",
        "cancel": "취소",
        "uncheck": "체크 해제하면 선택에서 제외됩니다.",
        "empty": "아직 선택한 폴더가 없습니다.",
        "empty_hint": "‘폴더 추가하기’를 눌러 PDF가 있는 폴더를 골라 주세요.",
        "selection_response_error": "폴더 목록의 선택을 완료하지 못했습니다.",
        "selection_json_error": "macOS 폴더 선택창이 올바른 선택 결과를 반환하지 않았습니다.",
        "selection_paths_error": "macOS 폴더 선택창이 올바른 폴더 경로 목록을 반환하지 않았습니다.",
        "picker_open_error": "macOS 폴더 선택창을 열 수 없습니다",
        "picker_stopped_error": "macOS 선택창 실행이 중단되었습니다.",
        "picker_launcher_error": "선택창 실행기를 시작하지 못했습니다.",
        "linux_title": "PDF를 찾아볼 폴더를 선택하세요",
        "linux_open_error": "폴더 선택창을 열 수 없습니다",
        "unsupported_error": (
            "이 운영체제에서는 폴더 선택창을 자동으로 열 수 없습니다. "
            "source-add 명령 뒤에 폴더 경로를 지정해 주세요."
        ),
    },
    "en": {
        "picker_prompt": (
            "Choose folders to add to the list.\n"
            "Hold ⌘ Command and click to select multiple folders.\n"
            "Confirm the list to save PDFs and start visual review."
        ),
        "onboarding_message": (
            "Research Agent is installed.\n\n"
            "Connect folders now to save PDFs and start visual review?\n"
            "Original files will not be modified."
        ),
        "later": "Later",
        "choose": "Choose folders",
        "onboarding_open_error": "Could not open the folder connection dialog.",
        "onboarding_response_error": "Could not read the folder connection dialog response.",
        "activation_error": "Could not activate the folder chooser app.",
        "add_to_list": "Add to list",
        "picker_response_error": "The folder chooser did not complete the selection.",
        "local_folders_error": "Only local folders can be selected.",
        "selection_title": "Folders to connect",
        "selection_message": "Confirm to save PDFs from the selected folders and start visual review. Original files will not be modified.",
        "connect": "Connect and save PDFs",
        "add": "Add folders",
        "add_more": "Add more folders",
        "cancel": "Cancel",
        "uncheck": "Uncheck a folder to exclude it from this selection.",
        "empty": "No folders selected yet.",
        "empty_hint": "Click “Add folders” to choose folders containing PDFs.",
        "selection_response_error": "The folder list did not complete the selection.",
        "selection_json_error": "The macOS folder chooser returned an invalid selection result.",
        "selection_paths_error": "The macOS folder chooser returned an invalid folder path list.",
        "picker_open_error": "Could not open the macOS folder chooser",
        "picker_stopped_error": "The macOS folder chooser stopped.",
        "picker_launcher_error": "Could not start the folder chooser launcher.",
        "linux_title": "Choose a folder containing PDFs",
        "linux_open_error": "Could not open the folder chooser",
        "unsupported_error": (
            "The folder chooser is not available on this operating system. "
            "Specify a folder path after the source-add command."
        ),
    },
}

# Retain the deterministic Korean prompt for callers that display it directly.
PICKER_PROMPT = _UI_TEXT["ko"]["picker_prompt"]
_MACOS_LANGUAGE_SCRIPT = """
(() => {
  ObjC.import("Foundation");
  return JSON.stringify(ObjC.deepUnwrap($.NSLocale.preferredLanguages));
})()
""".strip()


def _supported_language(value: str) -> str | None:
    primary = value.strip().replace("_", "-").split("-", 1)[0].lower()
    return primary if primary in ("ko", "en") else None


def resolve_ui_language(language: str = "auto") -> str:
    """Resolve app-owned dialog text without changing system preferences."""
    if language not in ("auto", "ko", "en"):
        raise ValueError("language must be auto, ko, or en")
    if language != "auto":
        return language
    if sys.platform == "darwin":
        # Installers may deliberately use LC_ALL=C. The macOS preference order
        # remains authoritative, and this Foundation-only query opens no UI.
        try:
            completed = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", _MACOS_LANGUAGE_SCRIPT],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            preferred = json.loads(completed.stdout)
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            return "en"
        if not isinstance(preferred, list) or any(not isinstance(item, str) for item in preferred):
            return "en"
        for item in preferred:
            supported = _supported_language(item)
            if supported:
                return supported
        return "en"
    # Standard process locale variables provide a narrow fallback outside macOS.
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(name)
        if value:
            return _supported_language(value.split(".", 1)[0].split("@", 1)[0]) or "en"
    return "en"


def _ui_text(language: str) -> dict[str, str]:
    if language not in ("ko", "en"):
        raise ValueError("dialog script language must be ko or en")
    return _UI_TEXT[language]


def _script_text(language: str) -> str:
    return json.dumps(_ui_text(language), ensure_ascii=False)


def macos_onboarding_script(language: str = "ko") -> str:
    script_text = _script_text(language)
    return """
(() => {
  const ui = __UI_TEXT__;
  const app = Application.currentApplication();
  app.includeStandardAdditions = true;
  try {
    const choice = app.displayDialog(
      ui.onboarding_message,
      {
        withTitle: "Research Agent",
        buttons: [ui.later, ui.choose],
        defaultButton: ui.choose,
        cancelButton: ui.later
      }
    );
    return JSON.stringify(choice.buttonReturned === ui.choose);
  } catch (error) {
    if (error.number === -128) return JSON.stringify(false);
    throw error;
  }
})()
""".strip().replace("__UI_TEXT__", script_text)


def offer_source_selection(language: str = "auto") -> bool:
    """Ask once after installation; the caller decides whether GUI is appropriate."""
    language = resolve_ui_language(language)
    ui = _ui_text(language)
    if sys.platform != "darwin":
        return False
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", macos_onboarding_script(language)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError(ui["onboarding_open_error"]) from error
    try:
        selected = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(ui["onboarding_response_error"]) from error
    if not isinstance(selected, bool):
        raise RuntimeError(ui["onboarding_response_error"])
    return selected


def _macos_application_setup(language: str = "ko") -> str:
    error_text = json.dumps(_ui_text(language)["activation_error"], ensure_ascii=False)
    return """
  ObjC.import("AppKit");
  const app = $.NSApplication.sharedApplication;
  const permitsWindows = () => {
    const policy = Number(app.activationPolicy);
    return policy === Number($.NSApplicationActivationPolicyAccessory) ||
      policy === Number($.NSApplicationActivationPolicyRegular);
  };
  // Reapplying the current policy can return false despite a usable app.
  // Inspect the resulting policy, not the setter's transition result.
  if (!permitsWindows()) app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
  if (!permitsWindows()) {
    throw new Error(__ACTIVATION_ERROR__);
  }
""".strip().replace("__ACTIVATION_ERROR__", error_text)


def macos_picker_script(language: str = "ko") -> str:
    script_text = _script_text(language)
    return f"""
(() => {{
  const ui = {script_text};
  {_macos_application_setup(language)}
  const panel = $.NSOpenPanel.openPanel;
  panel.title = "Research Agent";
  panel.message = ui.picker_prompt;
  panel.prompt = ui.add_to_list;
  panel.canChooseFiles = false;
  panel.canChooseDirectories = true;
  panel.allowsMultipleSelection = true;
  panel.canCreateDirectories = false;
  panel.treatsFilePackagesAsDirectories = false;
  panel.resolvesAliases = true;

  if (app.respondsToSelector($.NSSelectorFromString("activate"))) {{
    app.activate;
  }} else {{
    app.activateIgnoringOtherApps(false);
  }}
  // Let the native modal lifecycle display the panel and make it key.
  const response = Number(panel.runModal);
  if (response === Number($.NSModalResponseCancel)) return JSON.stringify([]);
  if (response !== Number($.NSModalResponseOK)) {{
    throw new Error(ui.picker_response_error);
  }}
  const folders = [];
  const urls = panel.URLs;
  for (let index = 0; index < Number(urls.count); index++) {{
    const url = urls.objectAtIndex(index);
    if (!url.isFileURL) throw new Error(ui.local_folders_error);
    folders.push(ObjC.unwrap(url.path));
  }}
  return JSON.stringify(folders);
}})()
""".strip()


def macos_selection_script(language: str = "ko") -> str:
    """Keep an editable draft in one GUI process until explicitly confirmed."""
    script_text = _script_text(language)
    count_text = (
        'count + "개 폴더 선택됨"' if language == "ko" else
        'count + (count === 1 ? " folder selected" : " folders selected")'
    )
    return """
(() => {
  const ui = __UI_TEXT__;
  __APPLICATION_SETUP__
  if (app.respondsToSelector($.NSSelectorFromString("activate"))) {
    app.activate;
  } else {
    app.activateIgnoringOtherApps(false);
  }

  // No files or persistent preferences are written while editing this draft.
  let draft = [];
  let selectionChanged = () => {};
  ObjC.registerSubclass({
    name: "ResearchFolderSelectionTarget",
    superclass: "NSObject",
    methods: {
      "selectionChanged:": {
        types: ["void", ["id"]],
        implementation: function(sender) { selectionChanged(); }
      }
    }
  });
  const target = $.ResearchFolderSelectionTarget.alloc.init;

  function label(text, frame, secondary) {
    const field = $.NSTextField.alloc.initWithFrame(frame);
    field.stringValue = text;
    field.editable = false;
    field.selectable = true;
    field.bezeled = false;
    field.drawsBackground = false;
    field.font = $.NSFont.systemFontOfSize(13);
    field.textColor = secondary ? $.NSColor.secondaryLabelColor : $.NSColor.labelColor;
    field.cell.lineBreakMode = $.NSLineBreakByTruncatingMiddle;
    return field;
  }

  while (true) {
    const alert = $.NSAlert.alloc.init;
    alert.messageText = ui.selection_title;
    alert.informativeText = ui.selection_message;
    alert.icon = $.NSImage.imageNamed($.NSImageNameFolder);
    const connect = alert.addButtonWithTitle(ui.connect);
    const add = alert.addButtonWithTitle(draft.length ? ui.add_more : ui.add);
    const cancel = alert.addButtonWithTitle(ui.cancel);
    cancel.keyEquivalent = "\\u001b";
    const width = 580;
    const listHeight = 252;
    const view = $.NSView.alloc.initWithFrame(
      $.NSMakeRect(0, 0, width, draft.length ? listHeight + 66 : 132)
    );
    const boxes = [];
    let summary;

    if (draft.length) {
      summary = label("", $.NSMakeRect(0, listHeight + 40, width, 22), false);
      view.addSubview(summary);
      view.addSubview(label(
        ui.uncheck,
        $.NSMakeRect(0, listHeight + 17, width, 20), true
      ));
      const scroll = $.NSScrollView.alloc.initWithFrame($.NSMakeRect(0, 0, width, listHeight));
      scroll.hasVerticalScroller = true;
      scroll.hasHorizontalScroller = false;
      scroll.autohidesScrollers = true;
      scroll.borderType = $.NSBezelBorder;
      const rowHeight = 56;
      const contentHeight = Math.max(listHeight, draft.length * rowHeight);
      const content = $.NSView.alloc.initWithFrame($.NSMakeRect(0, 0, width - 20, contentHeight));
      draft.forEach((path, index) => {
        const rowY = contentHeight - (index + 1) * rowHeight;
        const basename = path.split("/").pop() || "/";
        const box = $.NSButton.alloc.initWithFrame($.NSMakeRect(8, rowY + 26, width - 44, 24));
        box.setButtonType($.NSButtonTypeSwitch);
        box.title = basename.replace(/[\\r\\n\\t]/g, " ");
        box.font = $.NSFont.systemFontOfSize(13);
        box.cell.lineBreakMode = $.NSLineBreakByTruncatingMiddle;
        box.toolTip = path;
        box.setAccessibilityLabel(basename + " — " + path);
        box.state = $.NSControlStateValueOn;
        box.target = target;
        box.action = $.NSSelectorFromString("selectionChanged:");
        content.addSubview(box);
        boxes.push(box);
        const detail = label(
          path.replace(/[\\r\\n\\t]/g, " "),
          $.NSMakeRect(28, rowY + 6, width - 64, 20), true
        );
        detail.toolTip = path;
        detail.setAccessibilityLabel(path);
        content.addSubview(detail);
      });
      scroll.documentView = content;
      scroll.contentView.scrollToPoint($.NSMakePoint(0, contentHeight - listHeight));
      scroll.reflectScrolledClipView(scroll.contentView);
      view.addSubview(scroll);
    } else {
      view.addSubview(label(ui.empty, $.NSMakeRect(0, 76, width, 24), false));
      view.addSubview(label(
        ui.empty_hint,
        $.NSMakeRect(0, 48, width, 24), true
      ));
    }

    const checkedPaths = () => draft.filter((path, index) =>
      Number(boxes[index].state) === Number($.NSControlStateValueOn)
    );
    selectionChanged = () => {
      const count = checkedPaths().length;
      connect.enabled = count > 0;
      connect.keyEquivalent = count ? "\\r" : "";
      add.keyEquivalent = count ? "" : "\\r";
      if (summary) summary.stringValue = __COUNT_TEXT__;
    };
    selectionChanged();
    alert.accessoryView = view;
    const response = Number(alert.runModal);
    if (response === Number($.NSAlertThirdButtonReturn) || response === Number($.NSModalResponseCancel)) {
      return JSON.stringify([]);
    }
    if (response !== Number($.NSAlertFirstButtonReturn) && response !== Number($.NSAlertSecondButtonReturn)) {
      throw new Error(ui.selection_response_error);
    }
    draft = checkedPaths();
    if (response === Number($.NSAlertFirstButtonReturn)) {
      // Also guard against an empty result if a synthetic response bypasses the disabled button.
      if (draft.length) return JSON.stringify(draft);
      continue;
    }
    const picked = JSON.parse(__PICK_FOLDERS__);
    for (const path of picked) {
      if (!draft.includes(path)) draft.push(path);
    }
  }
})()
""".strip().replace("__UI_TEXT__", script_text).replace(
        "__APPLICATION_SETUP__", _macos_application_setup(language)
    ).replace("__COUNT_TEXT__", count_text).replace(
        "__PICK_FOLDERS__", macos_picker_script(language)
    )


def _parse_macos_selection(stdout: str, language: str = "ko") -> list[Path]:
    ui = _ui_text(language)
    try:
        values = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(ui["selection_json_error"]) from error
    if not isinstance(values, list) or any(
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or not Path(value).is_absolute()
        for value in values
    ):
        raise RuntimeError(ui["selection_paths_error"])
    return list(dict.fromkeys(Path(value) for value in values))


def choose_sources(language: str = "auto") -> list[Path]:
    language = resolve_ui_language(language)
    ui = _ui_text(language)
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", macos_selection_script(language)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or "").strip() or ui["picker_stopped_error"]
            raise RuntimeError(
                f"{ui['picker_open_error']}: {detail[:500]}"
            ) from None
        except OSError:
            raise RuntimeError(
                f"{ui['picker_open_error']}: {ui['picker_launcher_error']}"
            ) from None
        return _parse_macos_selection(result.stdout, language)

    if sys.platform.startswith("linux") and shutil.which("zenity"):
        try:
            result = subprocess.run(
                [
                    "zenity",
                    "--file-selection",
                    "--directory",
                    f"--title={ui['linux_title']}",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            raise RuntimeError(f"{ui['linux_open_error']}: {error}") from error
        value = result.stdout.removesuffix("\n")
        return [Path(value)] if result.returncode == 0 and value else []

    raise RuntimeError(ui["unsupported_error"])
