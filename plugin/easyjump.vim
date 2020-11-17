if exists('g:loaded_easyjump')
    finish
endif
let g:loaded_easyjump = v:true

let s:dir_name = expand('<sfile>:p:h')

function! s:invoke(mode) abort
    let script_file_name = s:dir_name.'/../easyjump.py'
    let smart_case = get(g:, 'easyjump_smart_case', v:true)
    let label_chars = get(g:, 'easyjump_label_chars', '')
    let label_attrs = get(g:, 'easyjump_label_attrs', '')
    let text_attrs = get(g:, 'easyjump_text_attrs', '')
    let command = printf('/usr/bin/env python3 %s mouse %s %s %s %s on',
    \    shellescape(script_file_name),
    \    smart_case ? 'on' : 'off',
    \    shellescape(label_chars),
    \    shellescape(label_attrs),
    \    shellescape(text_attrs),
    \)
    let result = system(command)
    mode
    if v:shell_error != 0
        echoerr result
        return
    endif
    if result == ''
        if a:mode ==# 'o'
            call feedkeys("\<esc>")
        endif
        return
    endif
    " send mouse click
    call timer_start(0, {_ -> system('nohup '.result.' >/dev/null 2>&1 &')})
    " receive mouse click
    if getchar() != "\<LeftMouse>"
        return
    endif
    let winid = win_getid()
    if v:mouse_winid != winid
        if a:mode ==# 'v'
            return
        endif
        if a:mode ==# 'o'
            call feedkeys("\<esc>")
            return
        endif
        call win_gotoid(v:mouse_winid)
    endif
    if a:mode ==# 'v'
        normal! gv
    endif
    execute printf('normal! %dG%d|', v:mouse_lnum, v:mouse_col)
endfunction

command! -nargs=0 EasyJump call s:invoke('n')

nnoremap <silent> <Plug>EasyJump :call <SID>invoke('n')<CR>
if !hasmapto('<Plug>EasyJump', 'n')
    nmap <C-J> <Plug>EasyJump
endif

inoremap <silent> <Plug>EasyJump <C-O>:call <SID>invoke('i')<CR>
if !hasmapto('<Plug>EasyJump', 'i')
    imap <C-J> <Plug>EasyJump
endif

vnoremap <silent> <Plug>EasyJump :<C-U>call <SID>invoke('v')<CR>
if !hasmapto('<Plug>EasyJump', 'v')
    vmap <C-J> <Plug>EasyJump
endif

onoremap <silent> <Plug>EasyJump :call <SID>invoke('o')<CR>
if !hasmapto('<Plug>EasyJump', 'o')
    omap <C-J> <Plug>EasyJump
endif
