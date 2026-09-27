from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys


PICKER_PROMPT = (
    "목록에 추가할 폴더를 선택하세요.\n"
    "⌘ Command 키를 누른 채 클릭하면 여러 폴더를 고를 수 있습니다.\n"
    "선택한 뒤 목록에서 확인하고 연결합니다."
)


def macos_onboarding_script() -> str:
    return """
(() => {
  const app = Application.currentApplication();
  app.includeStandardAdditions = true;
  try {
    const choice = app.displayDialog(
      "Research Agent 설치가 완료됐어요.\\n\\n지금 PDF가 있는 폴더를 연결할까요?\\n원본 파일은 수정하지 않습니다.",
      {
        withTitle: "Research Agent",
        buttons: ["나중에 하기", "폴더 선택하기"],
        defaultButton: "폴더 선택하기",
        cancelButton: "나중에 하기"
      }
    );
    return JSON.stringify(choice.buttonReturned === "폴더 선택하기");
  } catch (error) {
    if (error.number === -128) return JSON.stringify(false);
    throw error;
  }
})()
""".strip()


def offer_source_selection() -> bool:
    """Ask once after installation; the caller decides whether GUI is appropriate."""
    if sys.platform != "darwin":
        return False
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", macos_onboarding_script()],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError("폴더 연결 안내창을 열 수 없습니다.") from error
    try:
        selected = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("폴더 연결 안내창의 응답을 확인할 수 없습니다.") from error
    if not isinstance(selected, bool):
        raise RuntimeError("폴더 연결 안내창의 응답을 확인할 수 없습니다.")
    return selected


def _macos_application_setup() -> str:
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
    throw new Error("폴더 선택창의 앱을 활성화할 수 없습니다.");
  }
""".strip()


def macos_picker_script() -> str:
    prompt = json.dumps(PICKER_PROMPT, ensure_ascii=False)
    return f"""
(() => {{
  {_macos_application_setup()}
  const panel = $.NSOpenPanel.openPanel;
  panel.title = "Research Agent";
  panel.message = {prompt};
  panel.prompt = "목록에 추가";
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
    throw new Error("폴더 선택창이 선택을 완료하지 못했습니다.");
  }}
  const folders = [];
  const urls = panel.URLs;
  for (let index = 0; index < Number(urls.count); index++) {{
    const url = urls.objectAtIndex(index);
    if (!url.isFileURL) throw new Error("로컬 폴더만 선택할 수 있습니다.");
    folders.push(ObjC.unwrap(url.path));
  }}
  return JSON.stringify(folders);
}})()
""".strip()


def macos_selection_script() -> str:
    """Keep an editable draft in one GUI process until explicitly confirmed."""
    return """
(() => {
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
    alert.messageText = "연결할 폴더";
    alert.informativeText = "선택한 폴더에서 PDF를 찾습니다. 원본 파일은 수정하지 않습니다.";
    alert.icon = $.NSImage.imageNamed($.NSImageNameFolder);
    const connect = alert.addButtonWithTitle("이 폴더들 연결하기");
    const add = alert.addButtonWithTitle(draft.length ? "폴더 더 추가하기" : "폴더 추가하기");
    const cancel = alert.addButtonWithTitle("취소");
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
        "체크 해제하면 선택에서 제외됩니다.",
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
      view.addSubview(label("아직 선택한 폴더가 없습니다.", $.NSMakeRect(0, 76, width, 24), false));
      view.addSubview(label(
        "‘폴더 추가하기’를 눌러 PDF가 있는 폴더를 골라 주세요.",
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
      if (summary) summary.stringValue = count + "개 폴더 선택됨";
    };
    selectionChanged();
    alert.accessoryView = view;
    const response = Number(alert.runModal);
    if (response === Number($.NSAlertThirdButtonReturn) || response === Number($.NSModalResponseCancel)) {
      return JSON.stringify([]);
    }
    if (response !== Number($.NSAlertFirstButtonReturn) && response !== Number($.NSAlertSecondButtonReturn)) {
      throw new Error("폴더 목록의 선택을 완료하지 못했습니다.");
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
""".strip().replace("__APPLICATION_SETUP__", _macos_application_setup()).replace(
        "__PICK_FOLDERS__", macos_picker_script()
    )


def _parse_macos_selection(stdout: str) -> list[Path]:
    try:
        values = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("macOS 폴더 선택창이 올바른 선택 결과를 반환하지 않았습니다.") from error
    if not isinstance(values, list) or any(
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or not Path(value).is_absolute()
        for value in values
    ):
        raise RuntimeError("macOS 폴더 선택창이 올바른 폴더 경로 목록을 반환하지 않았습니다.")
    return list(dict.fromkeys(Path(value) for value in values))


def choose_sources() -> list[Path]:
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", macos_selection_script()],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or "").strip() or "macOS 선택창 실행이 중단되었습니다."
            raise RuntimeError(
                f"macOS 폴더 선택창을 열 수 없습니다: {detail[:500]}"
            ) from None
        except OSError:
            raise RuntimeError(
                "macOS 폴더 선택창을 열 수 없습니다: 선택창 실행기를 시작하지 못했습니다."
            ) from None
        return _parse_macos_selection(result.stdout)

    if sys.platform.startswith("linux") and shutil.which("zenity"):
        try:
            result = subprocess.run(
                [
                    "zenity",
                    "--file-selection",
                    "--directory",
                    "--title=PDF를 찾아볼 폴더를 선택하세요",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            raise RuntimeError(f"폴더 선택창을 열 수 없습니다: {error}") from error
        value = result.stdout.removesuffix("\n")
        return [Path(value)] if result.returncode == 0 and value else []

    raise RuntimeError(
        "이 운영체제에서는 폴더 선택창을 자동으로 열 수 없습니다. "
        "source-add 명령 뒤에 폴더 경로를 지정해 주세요."
    )
