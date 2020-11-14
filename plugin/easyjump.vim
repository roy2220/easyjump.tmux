if exists('g:loaded_easyjump')
    finish
endif
let g:loaded_easyjump = v:true

let s:dir_name = expand('<sfile>:p:h')

function! s:execute() abort
    let script_file_name = s:dir_name.'/../easyjump.py'
    let label_chars = get(g:, 'easyjump_label_chars', '')
    let label_attrs = get(g:, 'easyjump_label_attrs', '')
    let text_attrs = get(g:, 'easyjump_text_attrs', '')
    let smart_case = get(g:, 'easyjump_smart_case', v:true)
    let command = printf('/usr/bin/env python3 %s mouse %s %s %s %s',
    \    shellescape(script_file_name),
    \    shellescape(label_chars),
    \    shellescape(label_attrs),
    \    shellescape(text_attrs),
    \    shellescape(smart_case ? 'on' : 'off'),
    \)
    normal! m'
    call system(command)
    redraw!
endfunction
command! -nargs=0 EasyJump call s:execute()

nnoremap <Plug>EasyJump :EasyJump<CR>
if !hasmapto('<Plug>EasyJump', 'n')
    nmap <C-J> <Plug>EasyJump
endif

inoremap <Plug>EasyJump <C-O>:EasyJump<CR>
if !hasmapto('<Plug>EasyJump', 'i')
    imap <C-J> <Plug>EasyJump
endif
