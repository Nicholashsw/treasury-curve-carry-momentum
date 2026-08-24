Attribute VB_Name = "BloombergDV01"
Option Explicit
'==============================================================================
'  BloombergDV01  -  standalone DV01-only pull
'
'  WHY THIS EXISTS
'   Bundling CONVENTIONAL_CTD_FORWARD_FRSK into the 5-field futures BDH array made
'   the request hang. On its own (single field) it returns fine. So this macro pulls
'   ONLY that field, ONE field per root, into its own CSV per root. It does not touch
'   your existing PX_SETTLE/VOLUME/OPEN_INT/roll-map files -- run this alongside them.
'
'  OUTPUT: one file per root, e.g. TY1_DV01.csv, with columns:  Date, DV01
'   -> TU1_DV01.csv  FV1_DV01.csv  TY1_DV01.csv  UXY1_DV01.csv  US1_DV01.csv  WN1_DV01.csv
'
'  Downstream: the notebook reads DV01 from the futures TS file's
'   CONVENTIONAL_CTD_FORWARD_FRSK column. These separate *_DV01.csv files use the same
'   column name, so you can either (a) load them as their own files, or (b) paste the
'   DV01 column back into each futures TS file. Tell me which and I'll match the loader.
'
'  HOW TO RUN
'   1. Alt+F11 -> import this as a NEW module (it is named BloombergDV01, so it will
'      NOT clash with your BloombergPull module -- keep both).
'   2. Check EXPORT_DIR below matches where your other CSVs go.
'   3. Run  Pull_DV01_Only.  Watch the status bar count 1/6 .. 6/6.
'   4. It pulls TEST first if TEST_MODE=True (2 roots, short range) so you can confirm
'      it's quick before the full six-root pull.
'==============================================================================

' ---------------------------- CONFIG -----------------------------------------
Private Const EXPORT_DIR   As String = "C:\BBG_Export\"    ' keep trailing backslash
Private Const TEST_MODE    As Boolean = True               ' True = 2 roots, 2025+; False = 6 roots, 2010+
Private Const FULL_START   As String = "1/1/2010"
Private Const TEST_START   As String = "1/1/2025"
Private Const WAIT_TIMEOUT As Long = 300                   ' single-field pull is light; 5 min is plenty
' -----------------------------------------------------------------------------

#If VBA7 Then
    Private Declare PtrSafe Sub Sleep Lib "kernel32" (ByVal ms As LongPtr)
#Else
    Private Declare Sub Sleep Lib "kernel32" (ByVal ms As Long)
#End If

Private Function Q() As String: Q = Chr(34): End Function

Public Sub Pull_DV01_Only()
    Dim roots As Variant
    If TEST_MODE Then
        roots = Array("TY1 Comdty", "TU1 Comdty")
    Else
        roots = Array("TU1 Comdty", "FV1 Comdty", "TY1 Comdty", _
                      "UXY1 Comdty", "US1 Comdty", "WN1 Comdty")
    End If

    EnsureDir
    Dim total As Long: total = UBound(roots) - LBound(roots) + 1
    Dim i As Long, k As Long, sec As String, ws As Worksheet, failed As String
    Dim startD As String: startD = IIf(TEST_MODE, TEST_START, FULL_START)

    For i = LBound(roots) To UBound(roots)
        k = k + 1
        sec = CStr(roots(i))
        SetStatus "DV01 (" & k & "/" & total & "): " & sec & " - requesting"
        Set ws = FreshSheet(SafeName(sec) & "_DV01")
        ws.Range("A1").Value = "Date"
        ws.Range("B1").Value = "CONVENTIONAL_CTD_FORWARD_FRSK"

        ' SINGLE-field BDH -> this is the form that returns quickly
        ws.Range("A2").Formula = "=BDH(" & Q & sec & Q & "," & _
            Q & "CONVENTIONAL_CTD_FORWARD_FRSK" & Q & "," & _
            Q & startD & Q & "," & Q & Q & "," & _
            Q & "Dts=S" & Q & "," & Q & "Sort=A" & Q & "," & Q & "Days=T" & Q & ")"

        If WaitForData(ws, "DV01 (" & k & "/" & total & "): " & sec) Then
            ws.UsedRange.Value = ws.UsedRange.Value             ' freeze
            SetStatus "DV01 (" & k & "/" & total & "): saving " & sec
            ExportSheet ws, SafeName(sec) & "_DV01"
        Else
            failed = failed & vbCrLf & "  " & sec
            ws.Range("A1").Value = "Date [DV01 TIMEOUT " & sec & "]"
        End If
        DoEvents
    Next i

    Application.StatusBar = False
    If Len(failed) = 0 Then
        MsgBox "DV01 pull complete: " & total & " files written to " & EXPORT_DIR, vbInformation
    Else
        MsgBox "DV01 pull done, but these timed out (re-run just them):" & failed & _
               vbCrLf & vbCrLf & "Others were written to " & EXPORT_DIR, vbExclamation
    End If
End Sub

'------------------------------- helpers -------------------------------------
Private Function WaitForData(ws As Worksheet, Optional statusPrefix As String = "") As Boolean
    Dim t As Single: t = Timer
    Dim lastShown As Long: lastShown = -1
    Do
        DoEvents
        Application.Calculate
        Dim v As Variant, r As Long, c As Long, pending As Boolean
        pending = False
        v = ws.Range(ws.Cells(1, 1), ws.Cells(8, 3)).Value     ' small top probe
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
        Dim el As Long: el = Int(Timer - t)
        If el <> lastShown And statusPrefix <> "" Then
            SetStatus statusPrefix & " ... waiting " & el & "s / " & WAIT_TIMEOUT & "s"
            lastShown = el
        End If
        Sleep 500
        If Timer - t > WAIT_TIMEOUT Then WaitForData = False: Exit Function
    Loop
End Function

Private Sub SetStatus(msg As String)
    Application.StatusBar = msg
    DoEvents
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
    If Len(s) > 26 Then s = Left(s, 26)              ' leave room for the _DV01 suffix
    SafeName = s
End Function

Private Sub ExportSheet(ws As Worksheet, fname As String)
    Dim wb As Workbook
    Set wb = Application.Workbooks.Add(xlWBATWorksheet)
    ws.UsedRange.Copy
    wb.Sheets(1).Range("A1").PasteSpecial xlPasteValuesAndNumberFormats
    Application.CutCopyMode = False
    Application.DisplayAlerts = False
    wb.SaveAs EXPORT_DIR & fname & ".csv", xlCSV
    wb.Close False
    Application.DisplayAlerts = True
End Sub

Private Sub EnsureDir()
    Dim p As String
    p = EXPORT_DIR
    If Right(p, 1) = "\" Then p = Left(p, Len(p) - 1)
    If Dir(p, vbDirectory) = "" Then MkDir p
End Sub
