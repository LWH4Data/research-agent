from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import unittest
from unittest import mock

from research_store.picker import (
    choose_sources,
    macos_onboarding_script,
    macos_picker_script,
    macos_selection_script,
    offer_source_selection,
)


class InstallDialogTests(unittest.TestCase):
    def test_macos_accepts_explicit_choice_and_cancellation(self) -> None:
        for selected in (True, False):
            with self.subTest(selected=selected), mock.patch(
                "research_store.picker.sys.platform", "darwin"
            ), mock.patch(
                "research_store.picker.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, json.dumps(selected), ""),
            ):
                self.assertIs(offer_source_selection(), selected)

    def test_malformed_dialog_result_is_not_a_choice(self) -> None:
        for value in ("", "null", "1", '"true"', "[]", "{}"):
            with self.subTest(value=value), mock.patch(
                "research_store.picker.sys.platform", "darwin"
            ), mock.patch(
                "research_store.picker.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, value, ""),
            ):
                with self.assertRaisesRegex(RuntimeError, "응답"):
                    offer_source_selection()

    def test_launch_failures_are_optional_onboarding_errors(self) -> None:
        for error in (OSError("no UI"), subprocess.CalledProcessError(1, ["osascript"])):
            with self.subTest(error=error), mock.patch(
                "research_store.picker.sys.platform", "darwin"
            ), mock.patch("research_store.picker.subprocess.run", side_effect=error):
                with self.assertRaisesRegex(RuntimeError, "안내창을 열 수 없습니다"):
                    offer_source_selection()

    def test_non_macos_never_opens_dialog(self) -> None:
        with mock.patch("research_store.picker.sys.platform", "linux"), mock.patch(
            "research_store.picker.subprocess.run"
        ) as run:
            self.assertFalse(offer_source_selection())
            run.assert_not_called()

    @unittest.skipUnless(sys.platform == "darwin", "macOS-only dialog compiler")
    def test_macos_onboarding_script_compiles_without_opening_ui(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                ["osacompile", "-l", "JavaScript", "-e", macos_onboarding_script(),
                 "-o", str(Path(directory) / "Onboarding.scpt")],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


class FolderPickerTests(unittest.TestCase):
    def macos_selection(self, stdout: str) -> list[Path]:
        with mock.patch("research_store.picker.sys.platform", "darwin"), mock.patch(
            "research_store.picker.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout, ""),
        ) as run:
            selected = choose_sources()
        self.assertEqual(run.call_args.args[0][:3], ["osascript", "-l", "JavaScript"])
        self.assertTrue(run.call_args.kwargs["check"])
        self.assertEqual(run.call_args.args[0][4], macos_selection_script())
        return selected

    def test_macos_accepts_three_folders(self) -> None:
        paths = [f"/tmp/research-agent-test{number}" for number in (1, 2, 3)]
        self.assertEqual(
            self.macos_selection(json.dumps(paths) + "\n"),
            [Path(path) for path in paths],
        )

    def test_macos_preserves_unicode_spaces_and_newlines_inside_paths(self) -> None:
        paths = ["/tmp/한글 자료", "/tmp/ leading and trailing ", "/tmp/line\nbreak\n"]
        self.assertEqual(
            self.macos_selection(json.dumps(paths, ensure_ascii=False) + "\n"),
            [Path(path) for path in paths],
        )

    def test_macos_accepts_one_folder(self) -> None:
        self.assertEqual(self.macos_selection('["/tmp/Papers"]\n'), [Path("/tmp/Papers")])

    def test_macos_cancellation_is_an_empty_list(self) -> None:
        self.assertEqual(self.macos_selection("[]\n"), [])

    def test_macos_deduplicates_confirmed_paths_in_selection_order(self) -> None:
        self.assertEqual(
            self.macos_selection('["/tmp/One", "/tmp/Two", "/tmp/One"]'),
            [Path("/tmp/One"), Path("/tmp/Two")],
        )

    def test_macos_rejects_malformed_json(self) -> None:
        for stdout in ("", "\n", "/tmp/Papers\n", '["/tmp/One"]\n["/tmp/Two"]', "["):
            with self.subTest(stdout=stdout), self.assertRaisesRegex(
                RuntimeError, "올바른 선택 결과"
            ):
                self.macos_selection(stdout)

    def test_macos_rejects_invalid_path_list_before_returning_any_selection(self) -> None:
        for values in (
            None,
            "/tmp/Papers",
            {"path": "/tmp/Papers"},
            ["/tmp/Valid", None],
            [False],
            [1],
            [["/tmp/Papers"]],
            [""],
            ["relative/path"],
            ["~/Papers"],
            [" "],
            ["/tmp/null\x00byte"],
        ):
            with self.subTest(values=values), self.assertRaisesRegex(
                RuntimeError, "올바른 폴더 경로 목록"
            ):
                self.macos_selection(json.dumps(values))

    def test_macos_launch_and_script_failures_are_reported(self) -> None:
        for error in (
            OSError("osascript unavailable"),
            subprocess.CalledProcessError(1, ["osascript"], stderr="picker failed"),
        ):
            with self.subTest(error=error), mock.patch(
                "research_store.picker.sys.platform", "darwin"
            ), mock.patch("research_store.picker.subprocess.run", side_effect=error):
                with self.assertRaisesRegex(RuntimeError, "macOS 폴더 선택창을 열 수 없습니다"):
                    choose_sources()

    def test_macos_script_error_tracebacks_do_not_echo_generated_script(self) -> None:
        script = macos_selection_script()
        for stderr in ("native picker failed", None, "", "   \n"):
            error = subprocess.CalledProcessError(
                1, ["osascript", "-l", "JavaScript", "-e", script], stderr=stderr
            )
            with self.subTest(stderr=stderr), mock.patch(
                "research_store.picker.sys.platform", "darwin"
            ), mock.patch("research_store.picker.subprocess.run", side_effect=error):
                try:
                    choose_sources()
                except RuntimeError as raised:
                    rendered = "".join(traceback.format_exception(raised))
                    self.assertIn("macOS 폴더 선택창을 열 수 없습니다", str(raised))
                    self.assertNotIn("ResearchFolderSelectionTarget", rendered)
                    self.assertNotIn("CalledProcessError", rendered)
                    self.assertNotIn("ObjC.import", rendered)
                    self.assertLess(len(str(raised)), 300)
                    if stderr and stderr.strip():
                        self.assertIn(stderr.strip(), str(raised))
                else:
                    self.fail("A failed picker must raise a concise error")

    def test_linux_keeps_single_selection_and_path_whitespace(self) -> None:
        path = "/tmp/ folder\nwith newline \n"
        with mock.patch("research_store.picker.sys.platform", "linux"), mock.patch(
            "research_store.picker.shutil.which", return_value="/usr/bin/zenity"
        ), mock.patch(
            "research_store.picker.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, path + "\n", ""),
        ):
            self.assertEqual(choose_sources(), [Path(path)])

    def test_linux_cancel_is_an_empty_list(self) -> None:
        with mock.patch("research_store.picker.sys.platform", "linux"), mock.patch(
            "research_store.picker.shutil.which", return_value="/usr/bin/zenity"
        ), mock.patch(
            "research_store.picker.subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, "", ""),
        ):
            self.assertEqual(choose_sources(), [])

    @unittest.skipUnless(sys.platform == "darwin", "macOS-only picker compiler")
    def test_macos_picker_script_compiles_without_opening_ui(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for name, script in (
                ("Picker", macos_picker_script()),
                ("Selection", macos_selection_script()),
            ):
                with self.subTest(script=name):
                    output = Path(directory) / f"{name}.scpt"
                    result = subprocess.run(
                        ["osacompile", "-l", "JavaScript", "-e", script, "-o", str(output)],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(sys.platform == "darwin", "macOS-only mocked JavaScript runtime")
class MacOSScriptBehaviorTests(unittest.TestCase):
    def run_script(
        self,
        script: str,
        response: object,
        *,
        fail_at: str | None = None,
        error_number: int | None = None,
        modal_response: str = "1",
        activation_allowed: bool = True,
        initial_policy: int = 2,
        activation_result_policy: int | None = None,
        modern_activation: bool = True,
        local_urls: bool = True,
        reviews: list[dict] | None = None,
        picks: list[dict] | None = None,
    ) -> dict:
        scenario = json.dumps({
            "script": script,
            "response": response,
            "failAt": fail_at,
            "errorNumber": error_number,
            "modalResponse": modal_response,
            "activationAllowed": activation_allowed,
            "initialPolicy": initial_policy,
            "activationResultPolicy": activation_result_policy,
            "modernActivation": modern_activation,
            "localURLs": local_urls,
            "reviews": reviews,
            "picks": picks,
        })
        # Shadow both JXA bridges so executing production scripts cannot open a GUI.
        harness = """
(() => {
  const scenario = SCENARIO;
  const calls = [];
  let pickIndex = 0;
  let reviewIndex = 0;
  function invoke(method, options, response) {
    calls.push({method, options});
    if (scenario.failAt === method) {
      const error = new Error("simulated failure");
      error.number = scenario.errorNumber;
      throw error;
    }
    return response;
  }
  const scriptingApp = {
    displayDialog: (prompt, options) => invoke("displayDialog", options, scenario.response)
  };
  const app = {
    activationPolicy: scenario.initialPolicy,
    setActivationPolicy(policy) {
      // AppKit can return false for an idempotent setter even while the
      // application's current policy already allows activation.
      const changed = Number(this.activationPolicy) !== Number(policy);
      const accepted = invoke("setActivationPolicy", policy, scenario.activationAllowed && changed);
      if (accepted) {
        this.activationPolicy = scenario.activationResultPolicy === null
          ? policy : scenario.activationResultPolicy;
      }
      return accepted;
    },
    respondsToSelector: () => scenario.modernActivation,
    get activate() { return invoke("activate", null, null); },
    activateIgnoringOtherApps: flag => invoke("activateLegacy", flag, null)
  };
  function openPanel() {
    const pick = scenario.picks ? scenario.picks[pickIndex++] : {
      paths: scenario.response, response: scenario.modalResponse
    };
    if (!pick) throw new Error("unexpected folder picker");
    return invoke("openPanel", null, {
      get runModal() {
        return invoke("runModal", {
          files: this.canChooseFiles, directories: this.canChooseDirectories,
          multiple: this.allowsMultipleSelection, create: this.canCreateDirectories,
          packages: this.treatsFilePackagesAsDirectories
        }, pick.response === undefined ? "1" : pick.response);
      },
      get URLs() {
        invoke("URLs", null, null);
        return {
          count: String(pick.paths.length),
          objectAtIndex: index => ({path: pick.paths[index], isFileURL: scenario.localURLs})
        };
      }
    });
  }
  function view(frame) {
    return {
      frame, cell: {}, subviews: [],
      addSubview(child) { this.subviews.push(child); },
      setButtonType(type) { this.buttonType = type; },
      setAccessibilityLabel(text) { this.accessibilityLabel = text; },
      contentView: {scrollToPoint(point) { this.position = point; }},
      reflectScrolledClipView() {}
    };
  }
  const viewClass = {get alloc() { return {initWithFrame: view}; }};
  function descendants(root) {
    if (!root) return [];
    return [root].concat(...root.subviews.map(descendants),
      root.documentView ? descendants(root.documentView) : []);
  }
  function makeAlert() {
    return {
      buttons: [],
      addButtonWithTitle(title) {
        const button = {title, enabled: true};
        this.buttons.push(button);
        return button;
      },
      get runModal() {
        const step = (scenario.reviews || [])[reviewIndex++];
        if (!step) throw new Error("unexpected review dialog");
        const items = descendants(this.accessoryView);
        const boxes = items.filter(item => item.buttonType === "switch");
        const initialEnabled = this.buttons[0].enabled;
        (step.unchecked || []).forEach(index => {
          boxes[index].state = "0";
          boxes[index].target.methods[boxes[index].action].implementation(boxes[index]);
        });
        (step.rechecked || []).forEach(index => {
          boxes[index].state = "1";
          boxes[index].target.methods[boxes[index].action].implementation(boxes[index]);
        });
        return invoke("review", {
          initialEnabled,
          buttons: this.buttons,
          rows: boxes.map(box => ({title: box.title, path: box.toolTip,
            accessibilityLabel: box.accessibilityLabel, checked: Number(box.state) === 1})),
          labels: items.filter(item => item.stringValue !== undefined).map(item => ({
            text: item.stringValue, path: item.toolTip, accessibilityLabel: item.accessibilityLabel
          })),
          scrollable: items.some(item => item.hasVerticalScroller === true)
        }, {connect: "1000", add: "1001", cancel: "1002", close: "0"}[step.action] || step.action);
      }
    };
  }
  const mockApplication = {currentApplication: () => scriptingApp};
  const mockObjC = {
    import: () => {}, unwrap: value => value,
    registerSubclass(definition) {
      mockBridge[definition.name] = {alloc: {init: {methods: definition.methods}}};
    }
  };
  const mockBridge = {
    NSApplication: {sharedApplication: app},
    NSOpenPanel: {get openPanel() { return openPanel(); }},
    NSApplicationActivationPolicyAccessory: "1",
    NSApplicationActivationPolicyRegular: "0",
    NSApplicationActivationPolicyProhibited: "2",
    NSModalResponseOK: "1",
    NSModalResponseCancel: "0",
    NSSelectorFromString: value => value,
    NSAlert: {get alloc() { return {get init() { return makeAlert(); }}; }},
    NSAlertFirstButtonReturn: "1000",
    NSAlertSecondButtonReturn: "1001",
    NSAlertThirdButtonReturn: "1002",
    NSView: viewClass, NSTextField: viewClass, NSButton: viewClass, NSScrollView: viewClass,
    NSFont: {systemFontOfSize: value => value},
    NSColor: {labelColor: "primary", secondaryLabelColor: "secondary"},
    NSImage: {imageNamed: value => value}, NSImageNameFolder: "folder",
    NSLineBreakByTruncatingMiddle: "truncate-middle", NSBezelBorder: "bezel",
    NSButtonTypeSwitch: "switch", NSControlStateValueOn: "1",
    NSMakeRect: (x, y, width, height) => ({x, y, width, height}),
    NSMakePoint: (x, y) => ({x, y})
  };
  try {
    const run = new Function("Application", "ObjC", "$", "return " + scenario.script);
    return JSON.stringify({calls, result: JSON.parse(run(mockApplication, mockObjC, mockBridge))});
  } catch (error) {
    return JSON.stringify({calls, errorNumber: error.number, errorMessage: error.message});
  }
})()
""".replace("SCENARIO", scenario)
        completed = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", harness],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_picker_activates_before_multiple_folder_selection(self) -> None:
        paths = ["/tmp/first", "/tmp/한글 자료", "/tmp/line\nbreak"]
        outcome = self.run_script(macos_picker_script(), paths)
        self.assertEqual(outcome["result"], paths)
        self.assertEqual(
            [call["method"] for call in outcome["calls"]],
            ["setActivationPolicy", "openPanel", "activate", "runModal", "URLs"],
        )
        self.assertEqual(outcome["calls"][0]["options"], "1")
        self.assertEqual(
            outcome["calls"][3]["options"],
            {"files": False, "directories": True, "multiple": True,
             "create": False, "packages": False},
        )

    def review_calls(self, outcome: dict) -> list[dict]:
        return [call["options"] for call in outcome["calls"] if call["method"] == "review"]

    def test_selection_starts_with_empty_review_and_cancel_does_not_open_picker(self) -> None:
        outcome = self.run_script(macos_selection_script(), [], reviews=[{"action": "cancel"}])
        self.assertEqual(outcome["result"], [])
        review = self.review_calls(outcome)[0]
        self.assertFalse(review["buttons"][0]["enabled"])
        self.assertEqual(review["buttons"][1]["title"], "폴더 추가하기")
        self.assertEqual(review["buttons"][1]["keyEquivalent"], "\r")
        self.assertEqual(review["rows"], [])
        self.assertNotIn("openPanel", [call["method"] for call in outcome["calls"]])

    def test_selection_returns_paths_only_after_explicit_final_confirmation(self) -> None:
        paths = ["/tmp/first", "/tmp/한글 자료", "/tmp/line\nbreak\n"]
        outcome = self.run_script(
            macos_selection_script(), [],
            reviews=[{"action": "add"}, {"action": "connect"}], picks=[{"paths": paths}],
        )
        self.assertEqual(outcome["result"], paths)
        reviews = self.review_calls(outcome)
        self.assertEqual([row["path"] for row in reviews[1]["rows"]], paths)
        self.assertEqual(reviews[1]["buttons"][0]["title"], "이 폴더들 연결하기")
        self.assertTrue(reviews[1]["buttons"][0]["enabled"])
        self.assertEqual(reviews[1]["buttons"][0]["keyEquivalent"], "\r")
        self.assertEqual(
            [call["method"] for call in outcome["calls"]],
            ["setActivationPolicy", "activate", "review", "openPanel",
             "activate", "runModal", "URLs", "review"],
        )

    def test_selection_can_add_deduplicate_and_exclude_before_connecting(self) -> None:
        outcome = self.run_script(
            macos_selection_script(), [],
            reviews=[{"action": "add"}, {"action": "add"},
                     {"action": "connect", "unchecked": [1]}],
            picks=[{"paths": ["/tmp/one", "/tmp/wrong"]},
                   {"paths": ["/tmp/one", "/tmp/three", "/tmp/three"]}],
        )
        self.assertEqual(outcome["result"], ["/tmp/one", "/tmp/three"])
        reviews = self.review_calls(outcome)
        self.assertEqual(len(reviews[-1]["rows"]), 3)
        self.assertEqual(reviews[1]["buttons"][1]["title"], "폴더 더 추가하기")
        self.assertIn("2개 폴더 선택됨", [label["text"] for label in reviews[-1]["labels"]])

    def test_inner_picker_cancel_keeps_existing_draft_and_does_not_read_cancelled_paths(self) -> None:
        outcome = self.run_script(
            macos_selection_script(), [],
            reviews=[{"action": "add"}, {"action": "add"}, {"action": "connect"}],
            picks=[{"paths": ["/tmp/keep"]}, {"paths": ["/tmp/unconfirmed"], "response": "0"}],
        )
        self.assertEqual(outcome["result"], ["/tmp/keep"])
        reviews = self.review_calls(outcome)
        self.assertEqual(reviews[1]["rows"], reviews[2]["rows"])
        self.assertEqual([call["method"] for call in outcome["calls"]].count("URLs"), 1)

    def test_first_picker_cancel_returns_to_empty_review(self) -> None:
        outcome = self.run_script(
            macos_selection_script(), [],
            reviews=[{"action": "add"}, {"action": "cancel"}],
            picks=[{"paths": ["/tmp/unconfirmed"], "response": "0"}],
        )
        self.assertEqual(outcome["result"], [])
        self.assertEqual([review["rows"] for review in self.review_calls(outcome)], [[], []])
        self.assertNotIn("URLs", [call["method"] for call in outcome["calls"]])

    def test_cancel_or_close_entire_flow_discards_nonempty_draft(self) -> None:
        for action in ("cancel", "close"):
            with self.subTest(action=action):
                outcome = self.run_script(
                    macos_selection_script(), [],
                    reviews=[{"action": "add"}, {"action": action}],
                    picks=[{"paths": ["/tmp/uncommitted"]}],
                )
                self.assertEqual(outcome["result"], [])

    def test_unchecking_all_disables_connect_and_cannot_return_an_empty_commit(self) -> None:
        outcome = self.run_script(
            macos_selection_script(), [],
            reviews=[{"action": "add"}, {"action": "connect", "unchecked": [0]},
                     {"action": "cancel"}], picks=[{"paths": ["/tmp/exclude"]}],
        )
        self.assertEqual(outcome["result"], [])
        reviews = self.review_calls(outcome)
        self.assertTrue(reviews[1]["initialEnabled"])
        self.assertFalse(reviews[1]["buttons"][0]["enabled"])
        self.assertEqual(reviews[1]["buttons"][1]["keyEquivalent"], "\r")
        self.assertIn("0개 폴더 선택됨", [label["text"] for label in reviews[1]["labels"]])
        self.assertEqual(reviews[2]["rows"], [])

    def test_rechecking_restores_connection_and_add_respects_current_exclusions(self) -> None:
        outcome = self.run_script(
            macos_selection_script(), [],
            reviews=[{"action": "add"}, {"action": "add", "unchecked": [0]},
                     {"action": "connect", "unchecked": [0], "rechecked": [0]}],
            picks=[{"paths": ["/tmp/exclude", "/tmp/keep"]}, {"paths": ["/tmp/new"]}],
        )
        self.assertEqual(outcome["result"], ["/tmp/keep", "/tmp/new"])
        self.assertTrue(self.review_calls(outcome)[-1]["buttons"][0]["enabled"])

    def test_many_rows_scroll_and_same_folder_names_keep_exact_paths(self) -> None:
        paths = [f"/tmp/location-{index}/Papers" for index in range(20)]
        paths.append("/tmp/한글 " + "긴 경로" * 30 + "/line\nbreak")
        outcome = self.run_script(
            macos_selection_script(), [],
            reviews=[{"action": "add"}, {"action": "connect"}], picks=[{"paths": paths}],
        )
        self.assertEqual(outcome["result"], paths)
        review = self.review_calls(outcome)[1]
        self.assertTrue(review["scrollable"])
        self.assertEqual([row["path"] for row in review["rows"]], paths)
        self.assertTrue(all(row["title"] == "Papers" for row in review["rows"][:20]))
        self.assertEqual(review["rows"][-1]["title"], "line break")
        self.assertEqual([label["path"] for label in review["labels"] if "path" in label], paths)
        self.assertTrue(all(path in row["accessibilityLabel"] for path, row in zip(paths, review["rows"])))

    def test_selection_unknown_response_is_an_error_without_opening_picker(self) -> None:
        outcome = self.run_script(macos_selection_script(), [], reviews=[{"action": "-1001"}])
        self.assertNotIn("result", outcome)
        self.assertIn("완료하지 못했습니다", outcome["errorMessage"])
        self.assertNotIn("openPanel", [call["method"] for call in outcome["calls"]])

    def test_selection_picker_error_does_not_return_a_partial_draft(self) -> None:
        outcome = self.run_script(
            macos_selection_script(), [],
            reviews=[{"action": "add"}, {"action": "add"}],
            picks=[{"paths": ["/tmp/keep"]}, {"paths": [], "response": "-1001"}],
        )
        self.assertNotIn("result", outcome)
        self.assertIn("완료하지 못했습니다", outcome["errorMessage"])

    def test_onboarding_preserves_accepted_choice(self) -> None:
        outcome = self.run_script(
            macos_onboarding_script(), {"buttonReturned": "폴더 선택하기"}
        )
        self.assertIs(outcome["result"], True)
        self.assertEqual(
            [call["method"] for call in outcome["calls"]], ["displayDialog"]
        )

    def test_picker_cancel_never_reads_selected_paths(self) -> None:
        outcome = self.run_script(macos_picker_script(), ["/tmp/unconfirmed"], modal_response="0")
        self.assertEqual(outcome["result"], [])
        self.assertNotIn("URLs", [call["method"] for call in outcome["calls"]])

    def test_picker_abort_and_unknown_responses_are_errors(self) -> None:
        for response in ("-1001", "-1000", "unexpected"):
            with self.subTest(response=response):
                outcome = self.run_script(macos_picker_script(), [], modal_response=response)
                self.assertNotIn("result", outcome)
                self.assertIn("완료하지 못했습니다", outcome["errorMessage"])
                self.assertNotIn("URLs", [call["method"] for call in outcome["calls"]])

    def test_disallowed_activation_policy_stops_before_opening_panel(self) -> None:
        for script in (macos_picker_script(), macos_selection_script()):
            for initial_policy in (2, -1):
                with self.subTest(script=script[:30], initial_policy=initial_policy):
                    outcome = self.run_script(
                        script, [], activation_allowed=False, initial_policy=initial_policy,
                    )
                    self.assertNotIn("result", outcome)
                    self.assertIn("활성화할 수 없습니다", outcome["errorMessage"])
                    self.assertEqual([call["method"] for call in outcome["calls"]], ["setActivationPolicy"])

    def test_already_active_policy_skips_setter_for_raw_picker_and_selection(self) -> None:
        for script in (macos_picker_script(), macos_selection_script()):
            for initial_policy in (0, 1):
                with self.subTest(script=script[:30], initial_policy=initial_policy):
                    outcome = self.run_script(
                        script, [], initial_policy=initial_policy, activation_allowed=False,
                        reviews=[{"action": "cancel"}],
                    )
                    self.assertEqual(outcome["result"], [])
                    self.assertNotIn("setActivationPolicy", [call["method"] for call in outcome["calls"]])

    def test_repeated_picker_openings_change_activation_policy_only_once(self) -> None:
        outcome = self.run_script(
            macos_selection_script(), [],
            reviews=[{"action": "add"}, {"action": "add"}, {"action": "add"}, {"action": "connect"}],
            picks=[{"paths": ["/tmp/one"]}, {"paths": [], "response": "0"}, {"paths": ["/tmp/two"]}],
        )
        self.assertEqual(outcome["result"], ["/tmp/one", "/tmp/two"])
        methods = [call["method"] for call in outcome["calls"]]
        self.assertEqual(methods.count("setActivationPolicy"), 1)
        self.assertEqual(methods.count("openPanel"), 3)

    def test_successful_setter_must_leave_an_activation_capable_policy(self) -> None:
        for script in (macos_picker_script(), macos_selection_script()):
            for result_policy in (2, -1):
                with self.subTest(script=script[:30], result_policy=result_policy):
                    outcome = self.run_script(
                        script, [], activation_result_policy=result_policy,
                        reviews=[{"action": "cancel"}],
                    )
                    self.assertNotIn("result", outcome)
                    self.assertIn("활성화할 수 없습니다", outcome["errorMessage"])
                    self.assertEqual([call["method"] for call in outcome["calls"]], ["setActivationPolicy"])

    def test_older_macos_uses_non_forcing_activation_fallback(self) -> None:
        outcome = self.run_script(macos_picker_script(), [], modern_activation=False)
        self.assertEqual(outcome["result"], [])
        self.assertEqual(outcome["calls"][2], {"method": "activateLegacy", "options": False})

    def test_non_local_urls_are_not_returned(self) -> None:
        outcome = self.run_script(macos_picker_script(), ["/tmp/remote"], local_urls=False)
        self.assertNotIn("result", outcome)
        self.assertIn("로컬 폴더", outcome["errorMessage"])

    def test_onboarding_cancel_remains_a_successful_skip(self) -> None:
        outcome = self.run_script(
            macos_onboarding_script(), {}, fail_at="displayDialog", error_number=-128
        )
        self.assertIs(outcome["result"], False)

    def test_native_errors_are_not_treated_as_cancellation(self) -> None:
        for script, fail_at in (
            (macos_picker_script(), "activate"),
            (macos_picker_script(), "runModal"),
            (macos_onboarding_script(), "displayDialog"),
        ):
            with self.subTest(fail_at=fail_at):
                outcome = self.run_script(script, [], fail_at=fail_at, error_number=-1743)
                self.assertEqual(outcome["errorNumber"], -1743)
                self.assertNotIn("result", outcome)


if __name__ == "__main__":
    unittest.main()
