(function () {
    'use strict';

    function parseAuthors(text) {
        return String(text || '')
            .split(/[;|]/)
            .map(function (s) { return s.trim(); })
            .filter(Boolean);
    }

    function parseTags(text) {
        return String(text || '')
            .split(',')
            .map(function (s) { return s.trim(); })
            .filter(Boolean);
    }

    function joinAuthors(values) {
        return values.join('; ');
    }

    function joinTags(values) {
        return values.join(', ');
    }

    function toOptions(names) {
        return names.map(function (name) {
            return { value: name, text: name };
        });
    }

    function initTokenSelect(config) {
        var backendInput = document.getElementById(config.backendInputId);
        var mount = document.getElementById(config.mountId);
        if (!backendInput || !mount || typeof TomSelect === 'undefined') {
            return null;
        }

        var ts = new TomSelect(mount, {
            plugins: ['remove_button'],
            persist: false,
            create: function (input, callback) {
                var value = String(input || '').trim();
                if (!value) {
                    callback();
                    return;
                }
                callback({ value: value, text: value });
            },
            maxItems: null,
            openOnFocus: true,
            placeholder: config.placeholder,
            options: toOptions(config.options || []),
            items: config.parseInitial(backendInput.value),
            render: {
                option: function (data, escape) {
                    return '<div class="py-1 px-2">' + escape(data.text) + '</div>';
                },
                item: function (data, escape) {
                    return '<div class="ts-chip">' + escape(data.text) + '</div>';
                },
            },
            onChange: function () {
                backendInput.value = config.join(this.getValue());
            },
        });

        ts.on('item_add', function () {
            backendInput.value = config.join(ts.getValue());
        });
        ts.on('item_remove', function () {
            backendInput.value = config.join(ts.getValue());
        });

        return ts;
    }

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.getElementById('source-form');
        if (!root || typeof TomSelect === 'undefined') {
            return;
        }

        var authorOptions = JSON.parse(document.getElementById('author-options-json').textContent || '[]');
        var tagOptions = JSON.parse(document.getElementById('tag-options-json').textContent || '[]');

        document.querySelectorAll('.source-token-fallback').forEach(function (el) {
            el.classList.add('d-none');
        });
        document.querySelectorAll('.token-select-mount').forEach(function (el) {
            el.classList.remove('d-none');
        });

        var authorsTs = initTokenSelect({
            mountId: 'authors-ts',
            backendInputId: 'id_authors_text',
            placeholder: 'Search or add authors...',
            options: authorOptions,
            parseInitial: parseAuthors,
            join: joinAuthors,
        });

        var tagsTs = initTokenSelect({
            mountId: 'tags-ts',
            backendInputId: 'id_tags_text',
            placeholder: 'Search or add tags...',
            options: tagOptions,
            parseInitial: parseTags,
            join: joinTags,
        });

        root.addEventListener('submit', function () {
            if (authorsTs) {
                document.getElementById('id_authors_text').value = joinAuthors(authorsTs.getValue());
            }
            if (tagsTs) {
                document.getElementById('id_tags_text').value = joinTags(tagsTs.getValue());
            }
        });
    });
})();
