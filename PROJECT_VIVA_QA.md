# GraderGent: Project Viva Questions and Answers

This guide is a preparation aid for explaining GraderGent to an instructor. Answers describe the current project and its bundled `add_two_integers` rules. You can shorten them during a presentation and expand them when asked follow-up questions.

## Project Overview

### 1. What is your project?

GraderGent is a rule-driven grading tool for C programming assignments. It compiles a student's source file, runs configured tests and analyses, calculates a weighted score, and generates a report with evidence and feedback.

### 2. What problem does it solve?

Manual grading of many similar programming submissions can be repetitive and inconsistent. GraderGent automates repeatable checks and gives students specific information about failures, while leaving instructor-defined rules and final judgment under human control.

### 3. Who are the intended users?

The main users are instructors and teaching assistants grading C assignments. Students can also use it as a pre-submission checker to find errors and understand areas to improve.

### 4. What is the project called?

The project is called GraderGent. The repository folder is named `AutoGrader`.

### 5. What assignment is currently configured?

The included rule set grades an `add_two_integers` problem. It asks a program to read two signed 32-bit integers and print their mathematically correct sum, which may require more than 32 bits.

### 6. What is the main benefit of the project?

It combines repeatable grading with actionable feedback. A report can show not only a score, but also which input failed, what output was expected, what the program produced, and which quality checks need attention.

### 7. Is GraderGent intended to replace instructors?

No. It automates defined checks and organizes evidence. Instructors still decide whether the rules are appropriate, review warnings such as similarity flags, and make any final academic judgment.

## User Workflow and Architecture

### 8. How does a user run the project?

The user can start the Gradio web interface with `python front_app.py`, or grade one or more files from the command line with `python front_app.py --cli FILE.c`. The CLI can also take a rules file using `--rules`.

### 9. What happens when a submission is graded?

The application loads and validates the rules, creates a temporary work directory, reads the source and problem data, compiles the submission, and performs a smoke run. It then dispatches configured analyzers, combines their results, and writes text and JSON reports.

### 10. What is the role of `front_app.py`?

`front_app.py` is the entry point. It handles the web interface and CLI, accepts source and rules files, invokes the grading coordinator, and displays or exports results. The main grading decisions are in `coordinator.py` and the analyzer modules.

### 11. What is the role of `coordinator.py`?

The coordinator manages one complete grading run: it loads problem files, conducts the initial compile and smoke checks, runs the configured analyzers, calculates the weighted grade, gathers failures and flags, and passes the report data to the report writer.

### 12. What does `rules_loader.py` do?

It parses the JSON rules file and checks that the metrics list is valid, metric names are unique, analyzer names exist, and weights are nonnegative with a positive total. If weights do not add to 1, the system normalizes them and adds a note to the report.

### 13. What is the role of the `analyzers/` directory?

It contains independent modules, generally one per grading metric. Each analyzer returns a score, evidence, feedback, and optionally suggestions or flags. The analyzer registry discovers modules so a new analyzer can be added without editing a central list.

### 14. What does the `Context` object contain?

It carries shared information for a grading run, including the source file and text, validated rules, temporary work directory, compiled binary path, problem statement, and configured time and memory limits. It also provides helpers for resolving rule paths and collecting known inputs.

### 15. Why use a coordinator and separate analyzers?

This separates orchestration from individual checks. The coordinator controls run order, parallelism, scoring, and reporting; each analyzer can focus on one concern and be configured or extended independently.

### 16. Why are some analyzers run in parallel?

Independent non-timing-sensitive checks can run concurrently to reduce grading time. The coordinator limits the worker pool, while timing-sensitive checks such as complexity estimation run alone to reduce interference in measurements.

### 17. What happens if a submission fails the initial checks?

If the source does not compile, or the smoke run times out, execution-based analyzers are skipped because they cannot produce meaningful results. Source-only analyzers can still run, and the report is marked partial with an explanatory flag.

### 18. What is a smoke run?

A smoke run executes the compiled submission on one sample input before the full analyzer suite. It is an early check for basic run failures and timeouts, not a proof that the program is correct.

## Rules and Scoring

### 19. How are grading criteria configured?

They are configured in a JSON rules file under `rules/`. The file names the problem, test directory, limits, edge cases, optional reference solution and LLM settings, and the metrics, parameters, and weights to use.

### 20. Can an instructor change grading rules without changing Python code?

Yes. The intended approach is to edit or upload a valid JSON rules file to adjust metrics, parameters, thresholds, limits, or weights. Adding a completely new kind of metric requires an analyzer module as well as a rule entry.

### 21. How is the final grade calculated?

Each analyzer returns a score from 0 to 1. The coordinator multiplies each normalized metric weight by its score, sums the contributions, and scales the result to 100:

`grade = 100 * sum(weight * score) / sum(weights)`

### 22. What does a metric weight mean?

It controls how much that metric contributes to the final grade. In the bundled add rules, correctness has a weight of 20%, and each of the other eight metrics has a weight of 10%.

### 23. What metrics are enabled for the bundled add problem?

The rule set checks correctness, compiler warnings, code structure, modularity, edge cases, estimated complexity, memory safety, readability, and originality.

### 24. How can the project support a new programming problem?

Add the problem statement, reference C solution, and input/output test pairs under `problems/<name>/`. Then create or adapt a JSON rules file with the paths, limits, edge cases, and metric configuration for that problem.

### 25. How can the project support a new metric?

Create an analyzer module under `analyzers/` with an `analyze(ctx, params)` function and the appropriate execution/timing declarations, then reference it by name in a rules file. The registry discovers analyzer modules automatically.

## The Analyzers

### 26. How does the correctness analyzer work?

`io_tests` runs the compiled submission against each configured `.in` test and compares its output with the matching `.out` file. Its score is the fraction of tests passed, and failures include the input, expected output, and actual output.

### 27. How is output compared?

The tests use the shared output-comparison helper in `utils.py`. The report records shortened versions of the input and outputs so a student can inspect failures without receiving excessively large text.

### 28. What does the compiler-warning metric measure?

`compiler_warnings` compiles the source using the configured GCC warning flags, counts warnings, and reduces the metric score by a configured penalty per warning. Compilation errors give that metric a zero score.

### 29. Why does the warning analyzer remove `-Werror`?

`-Werror` makes warnings fail compilation, which can prevent the analyzer from counting them. The analyzer removes that flag for its warning-counting pass while keeping the other configured flags.

### 30. What does static analysis check?

`static_analysis` checks function length and estimated cyclomatic complexity. If `cppcheck` is installed, it also includes findings from that tool; if it is absent, that optional part is skipped.

### 31. What is cyclomatic complexity?

It is a rough count of the independent paths through a function, often increased by decisions such as conditionals and loops. In this project it is used as one code-structure indicator, not as a correctness measurement.

### 32. What does the modularity analyzer check?

`function_split` checks whether helper functions exist and are called by another function. An unused helper does not count as evidence of modularity. The rules can also say helpers are not required for a problem.

### 33. How are edge cases tested?

`edge_case_runner` gets named inputs from the rules and compares the student's output against output from the instructor's compiled reference solution. The reference solution, rather than the LLM, determines expected outputs.

### 34. What edge cases are configured for the add problem?

The rules include negative numbers, zero values, and boundary values intended to test integer overflow. These cases are run against the reference solution and the student's submission.

### 35. What are LLM-generated counter-tests?

They are optional extra inputs proposed by the local LLM to try to expose defects. In the bundled rules, five are requested. They are reported as counter-examples but do not change the score unless `extra_cases_count_in_score` is explicitly enabled.

### 36. How does the complexity analyzer work?

It generates inputs at configured sizes, runs the program multiple times per size, uses median wall-clock times, subtracts a startup baseline, and estimates a growth class from the timing curve. It is an empirical estimate, not a formal proof of complexity.

### 37. Why are complexity results approximate?

Process startup time, machine load, small input sizes, and timer resolution can hide or distort runtime growth. The project uses repeats, medians, a baseline, and a noise floor to reduce some noise, but cannot eliminate it.

### 38. What does the sanitizer analyzer detect?

`sanitizer_run` rebuilds the program with AddressSanitizer and UndefinedBehaviorSanitizer, then runs it on known test and edge-case inputs. It reports issues detected by the sanitizers, including memory errors and some forms of undefined behavior.

### 39. Does a clean sanitizer run prove the program has no memory bugs?

No. It only means the configured runs did not detect a sanitizer issue. A bug may require an input that was not tested or a runtime path that was not exercised.

### 40. How is readability evaluated?

`llm_review` asks a locally hosted Ollama model to review the code against a prompt-based rubric and return a score and suggestions. If Ollama is unavailable or its response is unusable, a simple heuristic based on comments, identifier lengths, and line lengths is used and flagged.

### 41. What does the originality analyzer do?

It normalizes C source tokens and compares token 4-gram sets with files in a configured corpus using Jaccard similarity. A corpus match over the threshold is flagged and affects that metric's score. An optional comparison to LLM-generated solutions is advisory and does not lower the score.

### 42. Does a similarity flag prove plagiarism?

No. Similarity is a signal for human review, not proof. Short or simple programs can independently look alike, and changed or obfuscated copied code can evade the threshold.

## LLM, Reproducibility, and Reports

### 43. What does the LLM do in this project?

The local model can review readability, explain selected failing inputs, and propose extra counter-test inputs. The project also optionally compares submissions with LLM-generated solutions as an advisory originality signal.

### 44. Is the LLM responsible for the whole grade?

No. Most metrics use deterministic programmatic checks. The configured LLM readability score contributes to the grade, but LLM-generated counter-tests do not affect it by default, LLM similarity is advisory, and reference outputs come from the instructor's solution.

### 45. What happens if Ollama is unavailable?

The project continues grading. The readability analyzer falls back to a heuristic, and LLM-dependent explanations, extra tests, or LLM-copy checks may be skipped. The report adds flags so the instructor can see where the LLM was unavailable.

### 46. How does the project improve repeatability?

It uses fixed tests and rules, normalizes metric weights, records a hash of the rules, and sends a fixed LLM temperature and seed. LLM responses are cached using the model settings and prompts, so repeated requests can reuse the same response.

### 47. Does a fixed LLM seed guarantee identical results in every environment?

Not necessarily. It improves repeatability, and the cache stabilizes repeated requests, but model versions and runtime environments can differ. The report records relevant model settings to make the evaluation easier to inspect.

### 48. What reports does GraderGent produce?

It writes a student-readable text report and a machine-readable JSON report. The web interface can also export reports as PDF or Excel files.

### 49. What information is in the report?

The report includes the overall grade, per-metric scores and weights, evidence, failing inputs, expected and actual output, suggestions, flags, and usefulness/limitations notes. The JSON report also includes metadata such as submission and rules hashes and tool/model versions.

### 50. Why provide both text and JSON reports?

Text is easy for students and instructors to read directly. JSON preserves structured evidence that other programs, dashboards, or analysis scripts can process.

## Execution and Safety

### 51. How does the sandbox limit a submitted program?

On Linux, `sandbox.py` applies time, CPU, virtual-memory, and output-file limits, runs the program in its own process session, uses temporary files for standard input/output/error, and kills the process group when needed.

### 52. Is the sandbox a security boundary for malicious programs?

No. It is designed to contain common bugs such as timeouts, crashes, excessive memory use, and excessive output. The project documentation explicitly recommends running GraderGent inside a Docker container or virtual machine before processing untrusted submissions on a shared machine.

### 53. Why are temporary files used for program I/O?

The sandbox routes input, output, and error through temporary files rather than relying on pipes that could fill and block. It also caps how much output is retained for the report.

### 54. Why is the sanitizer run configured differently for memory limits?

AddressSanitizer may reserve a large virtual address space, so the sanitizer analyzer disables the normal virtual-memory limit for those runs. It still uses a bounded runtime and runs inside the broader host/container environment.

### 55. What operating system and compiler does the current project target?

The sandbox implementation is Linux-oriented and uses GCC to compile C11 submissions. The README gives Ubuntu/Debian setup instructions. `cppcheck` is optional, and Gradio is used for the web interface.

### 56. Which programming languages are currently graded?

C is currently supported by the grading engine. The UI can display syntax choices for other languages, but selecting them does not enable grading; the application rejects analysis unless C is selected.

## Limitations and Future Improvements

### 57. Can a passing test suite prove a submission is correct?

No. Tests sample behavior for selected inputs. A program can pass all available tests and still fail on untested inputs, so stronger test coverage and instructor review remain important.

### 58. What are the main limitations of similarity detection?

It can produce false positives for short, common solutions and false negatives when copied code is sufficiently changed. The threshold is a triage setting, not a reliable verdict.

### 59. What are the main limitations of LLM-based review?

LLM feedback is subjective, depends on the selected model and prompt, and may be inconsistent or manipulated by source comments. The project detects some prompt-injection-like comments and flags the condition, but that cannot guarantee the model will always behave correctly.

### 60. What would you improve next?

Possible improvements include stronger container isolation, larger and more representative test sets, better-configured complexity workloads, support for more languages, improved similarity methods, and instructor review tools for investigating flagged submissions.

### 61. What is the most important caveat to explain to an instructor?

GraderGent is a decision-support tool, not an infallible judge. Test and timing results have limits, similarity flags need human review, LLM feedback is fallible, and the current sandbox is not a security boundary.

## Short Presentation Script

> GraderGent is a rule-driven grading tool for C assignments. An instructor configures tests, edge cases, limits, and metric weights in a JSON file. When a submission is analyzed, the tool compiles it, performs a smoke run, and dispatches analyzers for correctness, warnings, structure, modularity, edge cases, complexity, memory safety, readability, and similarity. It combines the metric scores into a weighted grade and creates text and JSON reports with evidence and feedback. The web UI and command-line mode support different workflows. LLM features are optional and clearly flagged, and results such as complexity estimates and similarity matches are intended to support instructor review rather than replace it.

## Demo Checklist

1. Start the interface with `python front_app.py`, or run a sample with `python front_app.py --cli samples/add_basic.c`.
2. Select the add rules and inspect the configured metrics and weights.
3. Run a clean sample, then a buggy sample, and compare the reported score and failing inputs.
4. Open the text or JSON report and point out per-metric evidence and flags.
5. Explain that LLM-dependent results are marked and that timing and similarity results have limitations.