// KaTeX is vendored locally. Render only the article's explicit LaTeX delimiters.
export function renderMath(root=document.getElementById('blogView')) {
  if (!root || !window.katex) return;
  root.querySelectorAll('[data-latex]').forEach(element=>{
    window.katex.render(element.dataset.latex,element,{
      displayMode:element.dataset.display!=='inline',
      output:'htmlAndMathml',throwOnError:false,trust:false
    });
  });
  const texts=[];
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{
    acceptNode(text){
      if(!text.textContent.includes('\\(')||text.parentElement.closest('.katex,pre,code,script,style,textarea,[data-latex]')) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }
  });
  while(walker.nextNode()) texts.push(walker.currentNode);
  for(const text of texts){
    const value=text.textContent,fragment=document.createDocumentFragment();
    const pattern=/\\\(([\s\S]+?)\\\)/g;
    let offset=0;
    for(const match of value.matchAll(pattern)){
      fragment.append(document.createTextNode(value.slice(offset,match.index)));
      const inline=document.createElement('span');
      window.katex.render(match[1],inline,{output:'htmlAndMathml',throwOnError:false,trust:false});
      fragment.append(inline);
      offset=match.index+match[0].length;
    }
    fragment.append(document.createTextNode(value.slice(offset)));
    text.replaceWith(fragment);
  }
}
