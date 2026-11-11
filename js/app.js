(function () {
  var site = window.SITE;
  var main = document.getElementById('main');
  var menu = document.querySelector('.menu');
  var lightbox = document.querySelector('.lightbox');
  var lightboxImg = lightbox.querySelector('img');
  var phone = window.matchMedia('(max-width: 767px)');
  var current = [];   // photos in the gallery on screen
  var openIndex = -1; // photo shown in the lightbox

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      if (key === 'text') node.textContent = attrs[key];
      else node.setAttribute(key, attrs[key]);
    });
    (children || []).forEach(function (child) { node.appendChild(child); });
    return node;
  }

  // The homepage shows the highlights and has no menu item: the name links to it.
  var pages = [{ slug: '', title: 'Highlights', hidden: true, photos: function () { return site.highlights; } }]
    .concat(site.galleries.map(function (g) {
      // A category with children is a drop-down in the menu, not a page of its own.
      var children = (g.children || []).map(function (child) {
        return { slug: child.slug, title: child.title, videos: child.videos || [],
                 photos: function () { return child.photos; } };
      });
      return { slug: g.slug, title: g.title, note: g.note, children: children, videos: g.videos || [],
               photos: function () { return g.photos; } };
    }))
    .concat([{ slug: 'about', title: 'About', about: true }]);

  // ---------- Sidebar ----------

  var logo = document.querySelector('.logo');
  logo.appendChild(el('span', { class: 'brand', text: site.brand }));
  logo.appendChild(el('span', { class: 'tagline', text: site.tagline }));
  var siteTitle = site.brand + ' ' + site.tagline;

  pages.filter(function (page) { return !page.hidden; }).forEach(function (page, i) {
    var item = el('li', { style: '--i:' + i });
    if (page.about) item.className = 'gap';
    if (page.children && page.children.length) {
      var toggle = el('button', { type: 'button', class: 'category', 'aria-expanded': 'false' },
        [el('span', { text: page.title }), el('span', { class: 'arrow', 'aria-hidden': 'true' })]);
      var list = el('ul', { class: 'submenu', hidden: '' }, page.children.map(function (child) {
        return el('li', {}, [el('a', { href: '#/' + child.slug, text: child.title })]);
      }));
      toggle.addEventListener('click', function () {
        setCategory(toggle, toggle.getAttribute('aria-expanded') !== 'true');
      });
      item.appendChild(toggle);
      item.appendChild(list);
    } else {
      item.appendChild(el('a', { href: '#/' + page.slug, text: page.title }));
    }
    menu.appendChild(item);
  });

  function setCategory(toggle, open) {
    toggle.setAttribute('aria-expanded', String(open));
    toggle.nextElementSibling.hidden = !open;
  }

  // Pages reachable by address: top-level pages plus the galleries inside drop-downs.
  var routes = pages.reduce(function (all, page) {
    return all.concat(page.children && page.children.length ? page.children : [page]);
  }, []);

  var hamburger = document.querySelector('.hamburger');
  function setMenu(open) {
    document.body.classList.toggle('menu-open', open);
    hamburger.setAttribute('aria-expanded', String(open));
  }
  hamburger.addEventListener('click', function () {
    setMenu(!document.body.classList.contains('menu-open'));
  });

  // ---------- Pages ----------

  function sidewaysWheel(strip) {
    // A normal (vertical) mouse wheel moves the strip sideways.
    strip.addEventListener('wheel', function (event) {
      if (phone.matches || Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
      event.preventDefault();
      strip.scrollLeft += event.deltaY;
    }, { passive: false });
  }

  function renderVideos(page) {
    current = [];
    var strip = el('div', { class: 'strip', tabindex: '0', 'aria-label': page.title });
    page.videos.forEach(function (item) {
      var video = el('video', {
        src: item.src, poster: item.poster, width: item.w, height: item.h,
        controls: '', playsinline: '', preload: 'none', 'aria-label': item.caption
      });
      // Only one video plays at a time.
      video.addEventListener('play', function () {
        strip.querySelectorAll('video').forEach(function (other) { if (other !== video) other.pause(); });
      });
      strip.appendChild(el('figure', { class: 'photo' }, [video, el('figcaption', { text: item.caption })]));
    });
    sidewaysWheel(strip);
    main.replaceChildren(strip);
  }

  function renderGallery(page) {
    if (page.videos && page.videos.length) { renderVideos(page); return; }
    current = page.photos();
    if (!current.length) {
      main.replaceChildren(el('p', { class: 'empty', text: page.note || 'Coming soon.' }));
      return;
    }
    var strip = el('div', { class: 'strip', tabindex: '0', 'aria-label': page.title + ' photos' });
    current.forEach(function (photo, i) {
      var ratio = photo.w / photo.h;
      var img = el('img', {
        src: photo.s,
        srcset: photo.s + ' ' + Math.round(photo.w / 2) + 'w, ' + photo.l + ' ' + photo.w + 'w',
        sizes: '(max-width: 767px) 100vw, ' + Math.round(84 * ratio) + 'vh',
        width: photo.w,
        height: photo.h,
        alt: photo.caption || page.title,
        decoding: 'async'
      });
      if (i > 2) img.loading = 'lazy';
      img.addEventListener('load', function () { img.classList.add('loaded'); });
      if (img.complete) img.classList.add('loaded');
      var button = el('button', { type: 'button', 'aria-label': 'Enlarge photo ' + (i + 1) }, [img]);
      button.addEventListener('click', function () { if (!phone.matches) openLightbox(i); });
      strip.appendChild(el('figure', { class: 'photo' }, [button, el('figcaption', { text: photo.caption })]));
    });

    sidewaysWheel(strip);
    main.replaceChildren(strip);
  }

  function renderAbout() {
    current = [];
    var about = site.about;
    var intro = el('div', { class: 'intro' }, about.intro.map(function (text) { return el('p', { text: text }); }));
    var nodes = [el('h1', { text: 'About' }), intro];
    about.sections.concat([
      { title: 'Selected work', lines: site.events }
    ]).forEach(function (section) {
      nodes.push(el('h2', { text: section.title }));
      nodes.push(el('ul', {}, section.lines.map(function (line) { return el('li', { text: line }); })));
    });
    nodes.push(el('h2', { text: 'For all inquiries' }));
    nodes.push(el('ul', {}, [el('li', {}, [el('a', { href: 'mailto:' + site.email, text: site.email })])]));
    main.replaceChildren(el('article', { class: 'about' }, nodes));
  }

  function route() {
    var slug = location.hash.replace(/^#\/?/, '');
    var page = routes.filter(function (p) { return p.slug === slug; })[0] || routes[0];
    closeLightbox();
    setMenu(false);
    menu.querySelectorAll('a').forEach(function (link) {
      if (link.getAttribute('href') === '#/' + page.slug) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    // A drop-down opens by itself when one of its galleries is on screen.
    menu.querySelectorAll('.category').forEach(function (toggle) {
      var active = !!toggle.nextElementSibling.querySelector('[aria-current]');
      toggle.classList.toggle('active', active);
      if (active) setCategory(toggle, true);
    });
    document.title = (page.slug ? page.title + ' - ' : '') + siteTitle;
    if (page.about) renderAbout(); else renderGallery(page);
    window.scrollTo(0, 0);
  }

  // ---------- Lightbox ----------

  function openLightbox(i) {
    openIndex = (i + current.length) % current.length;
    lightboxImg.src = current[openIndex].l;
    lightboxImg.alt = current[openIndex].caption || '';
    lightbox.hidden = false;
  }

  function closeLightbox() {
    if (openIndex < 0) return;
    var photo = main.querySelectorAll('.photo')[openIndex];
    openIndex = -1;
    lightbox.hidden = true;
    lightboxImg.removeAttribute('src');
    if (photo) photo.scrollIntoView({ inline: 'center', block: 'nearest' });
  }

  lightbox.addEventListener('click', closeLightbox);
  lightbox.querySelector('.lb-prev').addEventListener('click', function (event) {
    event.stopPropagation(); openLightbox(openIndex - 1);
  });
  lightbox.querySelector('.lb-next').addEventListener('click', function (event) {
    event.stopPropagation(); openLightbox(openIndex + 1);
  });

  document.addEventListener('keydown', function (event) {
    var strip = main.querySelector('.strip');
    if (openIndex >= 0) {
      if (event.key === 'Escape') closeLightbox();
      if (event.key === 'ArrowLeft') openLightbox(openIndex - 1);
      if (event.key === 'ArrowRight') openLightbox(openIndex + 1);
    } else if (strip && !phone.matches) {
      if (event.key === 'ArrowRight') strip.scrollBy({ left: window.innerWidth * 0.5, behavior: 'smooth' });
      if (event.key === 'ArrowLeft') strip.scrollBy({ left: -window.innerWidth * 0.5, behavior: 'smooth' });
    }
  });

  window.addEventListener('hashchange', route);
  route();
})();
