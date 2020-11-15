if exists('g:loaded_easyjump')
    finish
endif
let g:loaded_easyjump = v:true

let s:dir_name = expand('<sfile>:p:h')

command! -nargs=0 EasyJump call s:execute()
function! s:execute() abort
    let script_file_name = s:dir_name.'/../easyjump.py'
    let smart_case = get(g:, 'easyjump_smart_case', v:true)
    let label_chars = get(g:, 'easyjump_label_chars', '')
    let label_attrs = get(g:, 'easyjump_label_attrs', '')
    let text_attrs = get(g:, 'easyjump_text_attrs', '')
    let command = printf('/usr/bin/env python3 %s mouse %s %s %s %s on',
    \    shellescape(script_file_name),
    \    shellescape(smart_case ? 'on' : 'off'),
    \    shellescape(label_chars),
    \    shellescape(label_attrs),
    \    shellescape(text_attrs),
    \)
    let command = system(command)
    mode
    if v:shell_error != 0
        return
    endif
    if command == ''
        return
    endif
    normal! m'
    call system('nohup '.command.' >/dev/null 2>&1 &')
endfunction

nnoremap <Plug>EasyJump :EasyJump<CR>
if !hasmapto('<Plug>EasyJump', 'n')
    nmap <C-J> <Plug>EasyJump
endif

inoremap <Plug>EasyJump <C-O>:EasyJump<CR>
if !hasmapto('<Plug>EasyJump', 'i')
    imap <C-J> <Plug>EasyJump
endif
