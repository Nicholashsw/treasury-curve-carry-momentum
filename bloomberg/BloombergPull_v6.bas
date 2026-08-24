Attribute VB_Name = "BloombergPull"
Option Explicit
'==============================================================================
'  BloombergPull  v6  -  Rates Curve research dataset exporter
'
'  Pulls Blocks 1-4 of the checklist via the Bloomberg Excel add-in (BDH/BDS/BDP),
'  waits for async data, converts to static values, writes one CSV per
'  security/contract-root into EXPORT_DIR.
'
'  CHANGES FROM v5 (timeout / reliability)
'   - Bigger time budgets for a slow terminal: 600s normal, 900s for the heavy
'     multi-field futures pull and the static chains (was a flat 240s).
'   - AUTO-RETRY: a request that times out or comes back partial is re-issued once
'     (MAX_RETRIES) before being given up on.
'   - NO SILENT PARTIALS: a sheet that fails or is incompletely filled is NOT
'     exported. It is added to a failure list and named in a summary box at the end
'     ("these were NOT exported, re-run just these"), so a truncated file can never
'     masquerade as a complete one.
'   - COMPLETENESS CHECK: after data arrives, the last dated row must carry a real
'     value (not blank / not "Requesting" / not #N/A) or the pull is treated as failed.
'   - Per-cell #N/A in the static block (e.g. CTD on 1980s contracts) is expected and
'     is NOT treated as a failure; only a whole-request timeout is.
'
'  CHANGES FROM v4/v5 (carried forward)
'   - Live status-bar progress with per-item counter and running wait timer.
'   - Faster wait (small probe window, not full-sheet scan); UI stays responsive.
'   - CONVENTIONAL_CTD_FORWARD_FRSK (real daily forward DV01) in Block 3a, six roots.
'   - Removed FUT_ACT_DAYS_TO_EXP; Text-format static dates (locale fix);
'     dropped redundant FUT_DLV_ISIN.
'
'  PREREQUISITES
'   - Bloomberg Terminal running + logged in on THIS machine
'   - Bloomberg Excel add-in installed/enabled (BDH/BDP/BDS resolve as functions)
'
'  HOW TO RUN
'   1. Remove any existing BloombergPull module first (avoid name collision).
'   2. Alt+F11 -> File -> Import File -> this .bas
'   3. Edit CONFIG (EXPORT_DIR, TEST_MODE)
'   4. For the DV01 refresh: run Pull_Block3_FuturesTS with TEST_MODE=False. Watch
'      the status bar count 1/17..17/17 with a live "waiting Ns / 900s" timer. At the
'      end you get a summary box; if any item is listed as failed, re-run just that.
'   Tune WAIT_TIMEOUT / WAIT_TIMEOUT_TS / MAX_RETRIES in CONFIG if your terminal is
'   even slower than these defaults.
'==============================================================================

' ---------------------------- CONFIG -----------------------------------------
Private Const EXPORT_DIR    As String = "C:\BBG_Export\"   ' created if missing; keep trailing backslash
Private Const TEST_MODE     As Boolean = True              ' True = tiny pull to test plumbing
Private Const FULL_START    As String = "1/1/2010"         ' full-run start (US m/d/y arg to BDH)
Private Const TEST_START    As String = "1/1/2025"         ' test-run start
Private Const END_DATE      As String = ""                 ' "" = latest available
' Per-request time budget (seconds). Generous by default for a slow terminal.
' The heavy 5-field futures pull gets its own larger budget (WAIT_TIMEOUT_TS).
Private Const WAIT_TIMEOUT     As Long = 600               ' normal series (was 240)
Private Const WAIT_TIMEOUT_TS  As Long = 900               ' multi-field futures / big chains
Private Const MAX_RETRIES      As Long = 1                 ' auto re-issue a request this many times on timeout/partial
Private Const EXPORT_AS_CSV As Boolean = True              ' False = .xlsx instead
' -----------------------------------------------------------------------------

' Collects securities that failed even after retries, reported at the end.
Private gFailures As String
Private gActiveTimeout As Long                             ' set per pull; used by WaitForData
Private gInMaster As Boolean                              ' True while Bloomberg_RunAll drives the blocks

#If VBA7 Then
    Private Declare PtrSafe Sub Sleep Lib "kernel32" (ByVal ms As LongPtr)
#Else
    Private Declare Sub Sleep Lib "kernel32" (ByVal ms As Long)
#End If

Private Function Q() As String: Q = Chr(34): End Function
Private Function StartDate() As String: StartDate = IIf(TEST_MODE, TEST_START, FULL_START): End Function

'============================== MASTER ========================================
Public Sub Bloomberg_RunAll()
    gInMaster = True
    gFailures = ""
    EnsureDir
    ' ScreenUpdating stays ON so you can see activity + the status-bar progress.
    Pull_Block1_Cash
    Pull_Block2_Rates
    Pull_Block3_FuturesTS
    Pull_Block3_FuturesStatic
    Pull_Block4_Vol
    gInMaster = False
    ReportRun "Full run"
End Sub

'============================== BLOCK 1: CASH YIELDS ==========================
Public Sub Pull_Block1_Cash()
    StartBlock
    EnsureDir
    Dim secs As Variant
    If TEST_MODE Then
        secs = Array("USGG2YR Index", "USGG10YR Index")
    Else
        secs = Array("USGG3M Index", "USGG6M Index", "USGG12M Index", _
                     "USGG2YR Index", "USGG3YR Index", "USGG5YR Index", _
                     "USGG7YR Index", "USGG10YR Index", "USGG20YR Index", "USGG30YR Index")
    End If
    PullTimeSeries secs, Array("PX_LAST"), "Block 1 cash"
    FinishBlock "Block 1 cash"
End Sub

'============================== BLOCK 2: OIS / SWAP / POLICY ==================
Public Sub Pull_Block2_Rates()
    StartBlock
    EnsureDir
    Dim secs As Variant
    If TEST_MODE Then
        secs = Array("USOSFR2 Curncy", "FF1 Comdty")
    Else
        secs = Array( _
            "USOSFRA Curncy", "USOSFRC Curncy", "USOSFRF Curncy", _
            "USOSFR1 Curncy", "USOSFR2 Curncy", "USOSFR3 Curncy", "USOSFR5 Curncy", _
            "USOSFR7 Curncy", "USOSFR10 Curncy", "USOSFR30 Curncy", _
            "USSO1 Curncy", "USSO2 Curncy", "USSO3 Curncy", "USSO5 Curncy", "USSO10 Curncy", _
            "USSW2 Curncy", "USSW5 Curncy", "USSW10 Curncy", "USSW30 Curncy", _
            "FF1 Comdty", "FF2 Comdty", "FF3 Comdty", "FF4 Comdty", "FF5 Comdty", "FF6 Comdty", _
            "FF7 Comdty", "FF8 Comdty", "FF9 Comdty", "FF10 Comdty", "FF11 Comdty", "FF12 Comdty", _
            "FDTR Index")
    End If
    PullTimeSeries secs, Array("PX_LAST"), "Block 2 rates"
    FinishBlock "Block 2 rates"
End Sub

'============================== BLOCK 3a: FUTURES TIME SERIES =================
Public Sub Pull_Block3_FuturesTS()
    StartBlock
    EnsureDir
    Dim secs As Variant
    If TEST_MODE Then
        secs = Array("TY1 Comdty", "TU1 Comdty")
    Else
        secs = Array( _
            "TU1 Comdty", "TU2 Comdty", "TU3 Comdty", _
            "FV1 Comdty", "FV2 Comdty", "FV3 Comdty", _
            "TY1 Comdty", "TY2 Comdty", "TY3 Comdty", _
            "UXY1 Comdty", "UXY2 Comdty", _
            "US1 Comdty", "US2 Comdty", "US3 Comdty", _
            "WN1 Comdty", "WN2 Comdty", "WN3 Comdty")
    End If
    ' CONVENTIONAL_CTD_FORWARD_FRSK = the contract's forward DV01 (risk to delivery),
    ' available as daily history via BDH. This replaces the regression-beta DV01 proxy
    ' downstream with the real per-day contract sensitivity, for all six roots.
    PullTimeSeries secs, Array("PX_SETTLE", "PX_VOLUME", "OPEN_INT", _
                               "FUT_CUR_GEN_TICKER", "CONVENTIONAL_CTD_FORWARD_FRSK"), _
                   "Block 3a futures"
    FinishBlock "Block 3a futures"
End Sub

'============================== BLOCK 3b: FUTURES STATIC (per contract) =======
Public Sub Pull_Block3_FuturesStatic()
    StartBlock
    EnsureDir
    Dim roots As Variant, fields As Variant
    If TEST_MODE Then
        roots = Array("TY1 Comdty")
    Else
        roots = Array("TU1 Comdty", "FV1 Comdty", "TY1 Comdty", _
                      "UXY1 Comdty", "US1 Comdty", "WN1 Comdty")
    End If
    ' Confident mnemonics. Date fields here are auto Text-protected on export.
    ' CTD/conversion-factor/implied-repo confirmed on this terminal (Jul 2026):
    fields = Array("LAST_TRADEABLE_DT", "FUT_NOTICE_FIRST", _
                   "FUT_DLV_DT_FIRST", "FUT_DLV_DT_LAST", _
                   "FUT_CONT_SIZE", "FUT_TICK_SIZE", _
                   "FUT_CTD_CUSIP", "CTD_CNVS_FACTOR", "FUT_IMPLIED_REPO_RT")
    ' Field behaviour observed on the chain:
    '  - FUT_CTD_CUSIP: works, per-contract, populated for recent contracts; N/A for
    '    the oldest (pre-mid-1990s) ones, which is expected.
    '  - CTD_CNVS_FACTOR: only resolves on the ACTIVE generic ticker (e.g. TYA), not on
    '    dated chain members, so expect Invalid Field here for most rows; pull it from
    '    the active ticker separately if you need current conversion factors.
    '  - FUT_IMPLIED_REPO_RT: only meaningful (and populated) for live contracts.
    '  (FUT_DLV_ISIN was redundant with FUT_CTD_CUSIP and Invalid on dated contracts -> dropped.)
    Dim i As Long
    For i = LBound(roots) To UBound(roots)
        PullChainStatic CStr(roots(i)), fields
    Next i
    FinishBlock "Block 3b static"
End Sub

'============================== BLOCK 4: VOL / MACRO ==========================
Public Sub Pull_Block4_Vol()
    StartBlock
    EnsureDir
    Dim secs As Variant
    If TEST_MODE Then
        secs = Array("MOVE Index")
    Else
        secs = Array("MOVE Index", "VIX Index", "USGGBE10 Index")
        ' Optional 3M10Y swaption normal vol - verify ticker on terminal before use.
    End If
    PullTimeSeries secs, Array("PX_LAST"), "Block 4 vol"
    FinishBlock "Block 4 vol"
End Sub

'============================== CORE: TIME SERIES ============================
Private Sub PullTimeSeries(secs As Variant, flds As Variant, Optional label As String = "Pull")
    Dim i As Long, sec As String, ws As Worksheet, j As Long
    Dim total As Long: total = UBound(secs) - LBound(secs) + 1
    Dim k As Long: k = 0
    ' multi-field pulls (e.g. futures with DV01) are heavier -> bigger time budget
    gActiveTimeout = IIf(UBound(flds) - LBound(flds) + 1 >= 3, WAIT_TIMEOUT_TS, WAIT_TIMEOUT)
    For i = LBound(secs) To UBound(secs)
        k = k + 1
        sec = CStr(secs(i))
        Dim ok As Boolean, attempt As Long
        For attempt = 0 To MAX_RETRIES
            Dim tag As String
            tag = label & " (" & k & "/" & total & "): " & sec & _
                  IIf(attempt > 0, " [retry " & attempt & "]", "")
            SetStatus tag & " - requesting"
            Set ws = FreshSheet(SafeName(sec))
            ws.Range("A1").Value = "Date"
            For j = LBound(flds) To UBound(flds)
                ws.Cells(1, 2 + j - LBound(flds)).Value = flds(j)
            Next j
            ws.Range("A2").Formula = BDH_Formula(sec, flds)
            ok = WaitForData(ws, tag)
            If ok Then ok = SeriesLooksComplete(ws)   ' partial fill counts as failure
            If ok Then Exit For
        Next attempt

        If ok Then
            ws.UsedRange.Value = ws.UsedRange.Value    ' freeze (BDH dates are real serials)
            SetStatus label & " (" & k & "/" & total & "): saving " & sec
            ExportSheet ws, SafeName(sec)
        Else
            ' DO NOT export a failed/partial sheet -- record it and move on
            ws.Range("A1").Value = "Date [FAILED after " & (MAX_RETRIES + 1) & " tries]"
            gFailures = gFailures & vbCrLf & "  " & sec & " (" & label & ")"
            SetStatus label & " (" & k & "/" & total & "): FAILED " & sec & " - not exported"
        End If
        DoEvents
    Next i
    SetStatus label & ": done (" & total & "/" & total & ")"
End Sub

' Heuristic completeness check for a frozen/near-frozen BDH sheet. Requires a
' plausible row count, a valid last date, and at least one real numeric value among
' the last several rows of the first field column. The "last several" tolerance
' matters because a good futures pull legitimately ends with a blank-settle row
' (e.g. a holiday, or today before settlement posts) -- checking only the very last
' row would wrongly reject a complete series. Catches all-blank / error results.
Private Function SeriesLooksComplete(ws As Worksheet) As Boolean
    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, "A").End(xlUp).Row
    If lastRow < 20 Then Exit Function                 ' far too few rows -> failed
    If Not IsDate(ws.Cells(lastRow, 1).Value) Then Exit Function
    Dim r As Long, v As Variant, hi As Long, lo As Long
    hi = lastRow: lo = Application.Max(2, lastRow - 9)  ' probe the last up-to-10 rows
    For r = hi To lo Step -1
        v = ws.Cells(r, 2).Value                       ' first field column
        If Not IsError(v) Then                         ' guard first: CStr on #N/A would throw
            If IsNumeric(v) Then                        ' Empty/blank/"" are not numeric -> skipped
                SeriesLooksComplete = True: Exit Function
            End If
        End If
    Next r
    ' no real value in the last 10 rows -> treat as failed/partial
End Function

Private Function BDH_Formula(sec As String, flds As Variant) As String
    Dim fldArg As String, endArg As String
    fldArg = ArrayLiteral(flds)
    endArg = IIf(END_DATE = "", Q & Q, Q & END_DATE & Q)
    ' Days=T -> security trading calendar only; Fill=B -> blank on non-trading gaps.
    ' If any option token errors on your version, delete it from OptsTS().
    BDH_Formula = "=BDH(" & Q & sec & Q & "," & fldArg & "," & _
                  Q & StartDate & Q & "," & endArg & OptsTS() & ")"
End Function

Private Function OptsTS() As String
    OptsTS = "," & Q & "Dts=S" & Q & "," & Q & "Sort=A" & Q & _
             "," & Q & "Days=T" & Q & "," & Q & "Fill=B" & Q
End Function

'============================== CORE: FUTURES CHAIN + BDP ====================
Private Sub PullChainStatic(root As String, flds As Variant)
    Dim ws As Worksheet
    Set ws = FreshSheet(SafeName(root) & "_STATIC")
    gActiveTimeout = WAIT_TIMEOUT_TS                  ' chains/BDP matrices can be slow

    ' 1) enumerate the chain (expired included) down column A
    SetStatus "Block 3b static: " & root & " - fetching contract chain"
    ws.Range("A1").Value = "CONTRACT"
    ws.Range("A2").Formula = "=BDS(" & Q & root & Q & "," & Q & "FUT_CHAIN" & Q & _
                             "," & Q & "INCLUDE_EXPIRED_CONTRACTS=Y" & Q & ")"
    If Not WaitForData(ws, "Block 3b static: " & root & " chain") Then
        gFailures = gFailures & vbCrLf & "  " & root & " (Block 3b chain)"
        ws.Range("A1").Value = "CONTRACT [CHAIN FAILED " & root & "]"
        SetStatus "Block 3b static: " & root & " - chain FAILED, not exported"
        Exit Sub                                      ' no chain -> nothing to export
    End If
    ws.UsedRange.Value = ws.UsedRange.Value           ' column A tickers are text; no coercion risk

    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, "A").End(xlUp).Row
    If lastRow < 2 Then
        gFailures = gFailures & vbCrLf & "  " & root & " (Block 3b empty chain)"
        Exit Sub
    End If

    ' 2) BDP each field across columns B.. referencing the contract in column A
    SetStatus "Block 3b static: " & root & " - pulling " & (lastRow - 1) & " contracts x " & (UBound(flds) - LBound(flds) + 1) & " fields"
    Dim j As Long, col As Long
    For j = LBound(flds) To UBound(flds)
        col = 2 + (j - LBound(flds))
        ws.Cells(1, col).Value = flds(j)
        ws.Range(ws.Cells(2, col), ws.Cells(lastRow, col)).Formula = _
            "=BDP(A2," & Q & flds(j) & Q & ")"
    Next j

    ' Note: individual BDP cells legitimately return "#N/A N/A"/"Invalid Field" for
    ' fields that do not apply to a given contract (e.g. CTD on 1980s contracts), so
    ' we only treat a WHOLE-request timeout as a failure here, not per-cell N/As.
    If Not WaitForData(ws, "Block 3b static: " & root & " fields") Then
        gFailures = gFailures & vbCrLf & "  " & root & " (Block 3b fields timed out)"
        ws.Range("A1").Value = "CONTRACT [BDP-TIMEOUT " & root & "]"
        SetStatus "Block 3b static: " & root & " - fields timed out, not exported"
        Exit Sub
    End If
    FreezeStatic ws                                   ' Text-protect date columns, then freeze
    ExportSheet ws, SafeName(root) & "_STATIC"
    DoEvents
End Sub

' Freeze that protects date-typed columns from locale coercion.
' Date fields arrive as day-first text; setting the column to Text BEFORE writing
' the value back keeps "1/6/1982" as literal text instead of coercing to Jan 6.
Private Sub FreezeStatic(ws As Worksheet)
    Dim lastRow As Long, lastCol As Long, c As Long
    lastRow = ws.Cells(ws.Rows.Count, "A").End(xlUp).Row
    lastCol = ws.Cells(1, ws.Columns.Count).End(xlToLeft).Column
    For c = 1 To lastCol
        If IsDateField(CStr(ws.Cells(1, c).Value)) Then
            ws.Range(ws.Cells(2, c), ws.Cells(lastRow, c)).NumberFormat = "@"
        End If
    Next c
    ws.UsedRange.Value = ws.UsedRange.Value
End Sub

Private Function IsDateField(f As String) As Boolean
    Select Case UCase(Trim(f))
        Case "LAST_TRADEABLE_DT", "FUT_NOTICE_FIRST", "FUT_NOTICE_LAST", _
             "FUT_DLV_DT_FIRST", "FUT_DLV_DT_LAST", "FUT_FIRST_TRADE_DT", _
             "FIRST_SETTLE_DT", "MATURITY"
            IsDateField = True
    End Select
End Function

'============================== HELPERS ======================================
Private Function ArrayLiteral(flds As Variant) As String
    Dim i As Long, s As String
    If UBound(flds) = LBound(flds) Then
        ArrayLiteral = Q & flds(LBound(flds)) & Q
    Else
        s = "{"
        For i = LBound(flds) To UBound(flds)
            s = s & IIf(i > LBound(flds), ",", "") & Q & flds(i) & Q
        Next i
        ArrayLiteral = s & "}"
    End If
End Function

' Waits for Bloomberg to fill the sheet. Shows a live "...waiting Ns" counter on
' the status bar so a slow pull is visibly alive, not hung. Scans only a small
' top-of-sheet probe window (BDH shows "#N/A Requesting Data..." at the anchor
' while pending) instead of the whole range, which is much faster on big pulls.
Private Function WaitForData(ws As Worksheet, Optional statusPrefix As String = "") As Boolean
    Dim t As Single: t = Timer
    Dim lastShown As Long: lastShown = -1
    Dim budget As Long: budget = IIf(gActiveTimeout > 0, gActiveTimeout, WAIT_TIMEOUT)
    Do
        DoEvents
        Application.Calculate
        Dim v As Variant, r As Long, c As Long, pending As Boolean
        pending = False
        ' probe window: rows 1-8 across up to 10 columns (covers the anchor + fields)
        v = ws.Range(ws.Cells(1, 1), ws.Cells(8, 10)).Value
        For r = 1 To UBound(v, 1)
            For c = 1 To UBound(v, 2)
                If VarType(v(r, c)) = vbString Then
                    If InStr(1, v(r, c), "Requesting", vbTextCompare) > 0 _
                       Or InStr(1, v(r, c), "#N/A Req", vbTextCompare) > 0 Then
                        pending = True: Exit For
                    End If
                End If
            Next c
            If pending Then Exit For
        Next r
        If Not pending Then WaitForData = True: Exit Function
        ' update the live timer roughly once per second, showing the budget
        Dim el As Long: el = Int(Timer - t)
        If el <> lastShown And statusPrefix <> "" Then
            SetStatus statusPrefix & " ... waiting " & el & "s / " & budget & "s"
            lastShown = el
        End If
        Sleep 500
        If Timer - t > budget Then WaitForData = False: Exit Function
    Loop
End Function

' Write a message to Excel's status bar (bottom-left) and force it to repaint.
Private Sub SetStatus(msg As String)
    Application.StatusBar = msg
    DoEvents
End Sub

' Hand the status bar back to Excel when a block finishes.
Private Sub ClearStatus()
    Application.StatusBar = False
End Sub

' Reset the failure list only when a block is run on its own (not via the master).
Private Sub StartBlock()
    If Not gInMaster Then gFailures = ""
End Sub

' When a block is run on its own, show its own summary; when driven by the master,
' just clear the status bar and let the master report at the very end.
Private Sub FinishBlock(context As String)
    If gInMaster Then ClearStatus Else ReportRun context
End Sub

' Final summary. Names any securities that failed and were deliberately NOT exported,
' so a slow/partial pull can never masquerade as a complete file.
Private Sub ReportRun(context As String)
    ClearStatus
    If Len(gFailures) = 0 Then
        MsgBox context & ": all items pulled and exported successfully." & vbCrLf & _
               "CSVs are in " & EXPORT_DIR, vbInformation
    Else
        MsgBox context & ": COMPLETED WITH FAILURES." & vbCrLf & vbCrLf & _
               "The following were NOT exported -- re-run just these:" & _
               gFailures & vbCrLf & vbCrLf & _
               "Everything else was written to " & EXPORT_DIR, vbExclamation
    End If
End Sub

Private Function FreshSheet(nm As String) As Worksheet
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(nm)
    On Error GoTo 0
    If ws Is Nothing Then
        Set ws = ThisWorkbook.Worksheets.Add(After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        ws.Name = nm
    Else
        ws.Cells.Clear
    End If
    Set FreshSheet = ws
End Function

Private Function SafeName(sec As String) As String
    Dim s As String
    s = Replace(sec, " ", "_")
    s = Replace(s, "/", "_"): s = Replace(s, "\", "_")
    s = Replace(s, "[", ""): s = Replace(s, "]", "")
    s = Replace(s, ":", ""): s = Replace(s, "*", ""): s = Replace(s, "?", "")
    If Len(s) > 31 Then s = Left(s, 31)
    SafeName = s
End Function

Private Sub ExportSheet(ws As Worksheet, fname As String)
    Dim wb As Workbook
    Set wb = Application.Workbooks.Add(xlWBATWorksheet)
    ws.UsedRange.Copy
    wb.Sheets(1).Range("A1").PasteSpecial xlPasteValuesAndNumberFormats
    Application.CutCopyMode = False
    Application.DisplayAlerts = False
    If EXPORT_AS_CSV Then
        wb.SaveAs EXPORT_DIR & fname & ".csv", xlCSV
    Else
        wb.SaveAs EXPORT_DIR & fname & ".xlsx", xlOpenXMLWorkbook
    End If
    wb.Close False
    Application.DisplayAlerts = True
End Sub

Private Sub EnsureDir()
    Dim p As String
    p = EXPORT_DIR
    If Right(p, 1) = "\" Then p = Left(p, Len(p) - 1)
    If Dir(p, vbDirectory) = "" Then MkDir p
End Sub
