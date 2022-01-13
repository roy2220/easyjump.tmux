if exists('g:loaded_easyjump')
    finish
endif
let g:loaded_easyjump = v:true

let s:dir_name = expand('<sfile>:p:h')

function! s:invoke(mode) abort
    if !has('nvim')
        " change mouse protocol
        let temp = &ttymouse
        execute 'set ttymouse=urxvt'
    endif
    try
        call s:do_invoke(a:mode)
    finally
        if !has('nvim')
            " restore mouse protocol
            call timer_start(0, {_ -> execute('set ttymouse='.temp)})
        endif
    endtry
endfunction

function! s:do_invoke(mode) abort
    let script_file_name = s:dir_name.'/../easyjump.py'
    let cursor_pos = s:get_cursor_pos()
    let regions = s:get_regions()
    let key = s:get_key()
    if key == ''
        return
    endif
    let smart_case = get(g:, 'easyjump_smart_case', v:true)
    let label_chars = get(g:, 'easyjump_label_chars', '')
    let label_attrs = get(g:, 'easyjump_label_attrs', '')
    let text_attrs = get(g:, 'easyjump_text_attrs', '')
    let command = 'python3'
    \    .' '.shellescape(script_file_name)
    \    .' --cursor-pos='.join(cursor_pos, ',')
    \    .' --regions='.join(regions, ',')
    \    .' --key='.shellescape(key)
    \    .' --mode=mouse'
    \    .' --smart-case='.(smart_case ? 'on' : 'off')
    \    .' --label-chars='.shellescape(label_chars)
    \    .' --label-attrs='.shellescape(label_attrs)
    \    .' --text-attrs='.shellescape(text_attrs)
    \    .' --print-command-only=on'
    let result = system(command)
    mode
    if v:shell_error != 0
        echoerr result
        return
    endif
    if result == ''
        if a:mode ==# 'o'
            call feedkeys("\<esc>".(col('.') == 1 ? '' : 'l'))
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
    let [line, column] = [v:mouse_lnum, v:mouse_col]
    if a:mode ==# 'v' || a:mode ==# 'o'
        if v:mouse_winid != winid
            if a:mode ==# 'o'
                call feedkeys("\<esc>".(col('.') == 1 ? '' : 'l'))
            endif
            return
        endif
        if a:mode ==# 'v'
            let cur_pos = getcurpos()
            if line > cur_pos[1] || (line == cur_pos[1] && column > cur_pos[2])
                let column += 1
            endif
        endif
    else
        if v:mouse_winid != winid
            call win_gotoid(v:mouse_winid)
        endif
    endif
    if a:mode ==# 'v'
        normal! gv
    endif
    execute printf('normal! %dG%d|', line, column)
endfunction

function! s:get_key() abort
    let key = ''
    while len(key) < 2
        redraw | echo 'search for key (2 chars): '.key
        let c = getchar()
        if type(c) != v:t_number
            if c == "\<bs>"
                let key = ''
            endif
            continue
        endif
        let c = nr2char(c)
        if c == "\<esc>" || c == "\<cr>"
            redraw | echo ''
            return ''
        endif
        let key .= c
    endwhile
    redraw | echo ''
    return key
endfunction

function! s:get_cursor_pos() abort
    let [lnum, col] = getcurpos()[1:2]
    let screen_pos = screenpos(win_getid(), lnum, col)
    let cursor_pos = [screen_pos.col, screen_pos.row]
    return cursor_pos
endfunction

function! s:get_regions() abort
    let regions = []
    for winnr in range(1, winnr('$'))
        let winid = win_getid(winnr)
        let win_info = getwininfo(winid)[0]
        if win_info.terminal
            continue
        endif
        let region = [
        \    win_info.wincol,
        \    win_info.winrow,
        \    win_info.wincol + win_info.width - 1,
        \    win_info.winrow + win_info.height - 1,
        \]
        call extend(regions, region)
    endfor
    return regions
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

vnoremap <silent> <Plug>EasyJump <esc>:<C-U>call <SID>invoke('v')<CR>
if !hasmapto('<Plug>EasyJump', 'v')
    vmap <C-J> <Plug>EasyJump
endif

onoremap <silent> <Plug>EasyJump :call <SID>invoke('o')<CR>
if !hasmapto('<Plug>EasyJump', 'o')
    omap <C-J> <Plug>EasyJump
endif
